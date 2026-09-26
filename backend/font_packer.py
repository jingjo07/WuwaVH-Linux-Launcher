"""
WuWaVH Font Packer — Convert TTF/OTF to PAK v12 for Wuthering Waves

Reverse-engineered from Default_font_99_P.pak structure:
  [Entry Record: 53 bytes]  — offset/size/sha1 of the font data
  [Font Data: N bytes]      — Raw TrueType/OpenType font bytes
  [Suffix: 646 bytes]       — Index + PathHash + DirIndex + Footer
                               (contains file paths and offsets that must be updated)

The suffix contains 4 offset/size fields that reference the font data size:
  suffix[30:38]  — PathHash index offset  (= 53 + N + 127)
  suffix[70:78]  — FullDir index offset   (= 53 + N + 127 + 20)
  suffix[115:123] — Font data size reference (= N)
  footer[8:16]   — Index offset in footer (= 53 + N)
"""

import os
import struct
import hashlib
import shutil

# Known constants from the template PAK
_ENTRY_RECORD_SIZE = 53
_TEMPLATE_FONT_SIZE = 211084
_TEMPLATE_INDEX_SIZE = 127       # Index section size (constant, structure doesn't change)
_TEMPLATE_SUFFIX_SIZE = 646      # Everything after font data

# Offsets within the suffix where size/offset values live
_SUFFIX_OFF_PATHHASH   = 30   # u64: PathHash index offset (absolute in file)
_SUFFIX_OFF_FULLDIR    = 70   # u64: FullDir index offset (absolute in file)
_SUFFIX_OFF_FONTSIZE   = 115  # u64: font data size reference
_SUFFIX_OFF_FOOTER_SIG = 442  # Footer starts here (PAK magic 0x5A6F12E1)
_FOOTER_OFF_INDEX      = 8    # u64 index_offset within footer
_FOOTER_OFF_SHA1       = 24   # u8[20] index SHA1 within footer
_MAX_PREVIEW_FONT_SIZE = 20 * 1024 * 1024


def read_font_data_from_pak(pak_path: str) -> tuple[bytes, str]:
    """Read the embedded TTF/OTF used by a font PAK for launcher preview."""
    with open(pak_path, "rb") as pak:
        header = pak.read(_ENTRY_RECORD_SIZE + 4)
        if len(header) < _ENTRY_RECORD_SIZE + 4:
            raise ValueError("PAK font không hợp lệ")

        compressed_size = struct.unpack_from("<Q", header, 8)[0]
        font_size = struct.unpack_from("<Q", header, 16)[0]
        compression_method = struct.unpack_from("<I", header, 24)[0]
        if (compressed_size != font_size or compression_method != 0 or
                not 12 <= font_size <= _MAX_PREVIEW_FONT_SIZE or
                os.fstat(pak.fileno()).st_size < _ENTRY_RECORD_SIZE + font_size):
            raise ValueError("PAK không chứa font có thể xem trước")

        magic = header[_ENTRY_RECORD_SIZE:_ENTRY_RECORD_SIZE + 4]
        if magic not in (b"\x00\x01\x00\x00", b"OTTO"):
            raise ValueError("PAK không chứa font TTF/OTF")

        pak.seek(_ENTRY_RECORD_SIZE)
        font_data = pak.read(font_size)

    if len(font_data) != font_size:
        raise ValueError("Dữ liệu font trong PAK bị thiếu")
    mime = "font/otf" if magic == b"OTTO" else "font/ttf"
    return font_data, mime


def _get_template_path() -> str:
    from backend import game
    bundled = os.path.join(game.get_bundled_paks_dir(), "Default_font_99_P.pak")
    if os.path.isfile(bundled) and os.path.getsize(bundled) > 0:
        return bundled
    user_paks = game.get_paks_dir()
    return os.path.join(user_paks, "Default_font_99_P.pak")


def _ensure_template() -> str:
    template_path = _get_template_path()
    if not os.path.isfile(template_path) or os.path.getsize(template_path) == 0:
        from backend import downloader, game
        user_paks = game.get_paks_dir()
        target = os.path.join(user_paks, "Default_font_99_P.pak")
        os.makedirs(user_paks, exist_ok=True)
        ver_info = downloader.get_version_info()
        version = ver_info.get("version")
        href = downloader.mint_href("font", version)
        downloader.download_file(href, target)
        return target
    return template_path


def _read_template_suffix() -> bytes:
    """Read the suffix (index + pathhash + dirindex + footer) from template PAK."""
    template_path = _ensure_template()
    with open(template_path, "rb") as f:
        f.seek(_ENTRY_RECORD_SIZE + _TEMPLATE_FONT_SIZE)
        return f.read()


def _build_entry_record(font_data: bytes) -> bytes:
    """Build the 53-byte PAK entry record for the given font data."""
    size = len(font_data)
    sha1 = hashlib.sha1(font_data).digest()

    record = b""
    record += struct.pack("<Q", 0)       # offset (0 = start of file, entry points to itself)
    record += struct.pack("<Q", size)     # compressed_size
    record += struct.pack("<Q", size)     # uncompressed_size
    record += struct.pack("<I", 0)        # compression_method (none)
    record += sha1                        # SHA1 hash (20 bytes)
    record += struct.pack("<B", 0)        # flags (not encrypted)
    record += struct.pack("<I", 0)        # compression_block_size
    assert len(record) == _ENTRY_RECORD_SIZE
    return record


def _patch_suffix(suffix: bytearray, new_font_size: int) -> bytearray:
    """
    Patch all offset/size references in the suffix to match the new font data size.

    The suffix layout is fixed — only the numeric offset values change
    when the font data size changes.
    """
    new_index_offset = _ENTRY_RECORD_SIZE + new_font_size
    new_pathhash_offset = new_index_offset + _TEMPLATE_INDEX_SIZE
    new_fulldir_offset = new_pathhash_offset + 20  # PathHash section = 20 bytes

    # 1. PathHash index offset
    struct.pack_into("<Q", suffix, _SUFFIX_OFF_PATHHASH, new_pathhash_offset)

    # 2. FullDir index offset
    struct.pack_into("<Q", suffix, _SUFFIX_OFF_FULLDIR, new_fulldir_offset)

    # 3. Font data size reference
    struct.pack_into("<Q", suffix, _SUFFIX_OFF_FONTSIZE, new_font_size)

    # 4. Footer: index_offset
    footer_start = _SUFFIX_OFF_FOOTER_SIG
    struct.pack_into("<Q", suffix, footer_start + _FOOTER_OFF_INDEX, new_index_offset)

    # 5. Footer: index SHA1 — recompute from the patched index section
    #    The index section is the first _TEMPLATE_INDEX_SIZE bytes of suffix
    index_section = bytes(suffix[:_TEMPLATE_INDEX_SIZE])
    index_sha1 = hashlib.sha1(index_section).digest()
    suffix[footer_start + _FOOTER_OFF_SHA1 : footer_start + _FOOTER_OFF_SHA1 + 20] = index_sha1

    return suffix


def build_font_pak(font_file_path: str, output_path: str) -> str:
    """
    Convert a TTF/OTF font file into a PAK v12 file ready for Wuthering Waves.

    Args:
        font_file_path: Path to the source .ttf or .otf file
        output_path:    Path for the output .pak file

    Returns:
        The output_path on success

    Raises:
        FileNotFoundError: If the source font or template PAK doesn't exist
        ValueError: If the source file is not a valid font
    """
    if not os.path.isfile(font_file_path):
        raise FileNotFoundError(f"Font file không tồn tại: {font_file_path}")

    template_path = _ensure_template()
    if not os.path.isfile(template_path):
        raise FileNotFoundError(
            f"Không tìm thấy template PAK: {template_path}\n"
            "Hãy cập nhật Việt Hoá trước để tải file font mẫu."
        )

    # Read font data
    with open(font_file_path, "rb") as f:
        font_data = f.read()

    if len(font_data) < 12:
        raise ValueError("File font quá nhỏ hoặc bị hỏng")

    # Validate: TrueType starts with 00 01 00 00, OTF starts with 'OTTO'
    magic = font_data[:4]
    if magic not in (b"\x00\x01\x00\x00", b"OTTO"):
        raise ValueError(
            "File không phải font TTF/OTF hợp lệ. "
            f"Magic bytes: {magic.hex()}"
        )

    # Build the PAK
    entry_record = _build_entry_record(font_data)
    suffix = bytearray(_read_template_suffix())
    suffix = _patch_suffix(suffix, len(font_data))

    # Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(entry_record)
        f.write(font_data)
        f.write(suffix)

    return output_path


def get_font_name(font_file_path: str) -> str:
    """Extract a human-readable font name from the file path."""
    basename = os.path.splitext(os.path.basename(font_file_path))[0]
    # Clean up common suffixes
    for suffix in ["-Regular", "-Bold", "-Italic", "-Light", "-Medium",
                   "-SemiBold", "-ExtraBold", "-Black", "-Thin"]:
        if basename.endswith(suffix):
            basename = basename[:-len(suffix)] + f" ({suffix[1:]})"
            break
    return basename

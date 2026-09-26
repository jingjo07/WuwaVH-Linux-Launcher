"""Check GitHub releases and install a verified Launcher AppImage."""

import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.request

from backend import downloader
from backend.version import LAUNCHER_VERSION


RELEASE_API = "https://api.github.com/repos/jingjo07/WuwaVH-Linux-Launcher/releases/latest"
ASSET_NAME = "WuWaVH-Launcher-x86_64.AppImage"
MAX_DOWNLOAD_SIZE = 300 * 1024 * 1024
RELEASE_DOWNLOAD_PREFIX = "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/"


def _managed_appimage_path():
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(data_home, "wuwavh", ASSET_NAME)


def _install_target():
    """Replace a writable AppImage; otherwise use a persistent user-owned copy."""
    current = os.environ.get("APPIMAGE", "")
    if current:
        current = os.path.realpath(current)
        if os.path.isfile(current) and os.access(os.path.dirname(current), os.W_OK):
            return current
    return _managed_appimage_path()


def _version_parts(value):
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(value).strip(), re.I)
    if not match:
        raise ValueError("Phiên bản GitHub không hợp lệ")
    return tuple(int(part) for part in match.group(1).split("."))


def _is_newer(latest, current):
    latest_parts, current_parts = _version_parts(latest), _version_parts(current)
    length = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (length - len(latest_parts)) > current_parts + (0,) * (length - len(current_parts))


def check_update():
    request = urllib.request.Request(
        RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "WuWaVH-Launcher"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        release = json.load(response)

    tag = release.get("tag_name", "")
    newer = _is_newer(tag, LAUNCHER_VERSION)
    asset = next((item for item in release.get("assets", []) if item.get("name") == ASSET_NAME), None)
    can_install = bool(
        newer and asset
        and re.fullmatch(r"sha256:[a-fA-F0-9]{64}", asset.get("digest", ""))
        and asset.get("browser_download_url", "").startswith(RELEASE_DOWNLOAD_PREFIX)
    )
    return {
        "current_version": LAUNCHER_VERSION,
        "latest_version": tag.lstrip("vV"),
        "available": newer,
        "can_install": can_install,
        "release_url": release.get("html_url", ""),
        "asset_url": asset.get("browser_download_url", "") if asset else "",
        "asset_size": asset.get("size", 0) if asset else 0,
        "digest": asset.get("digest", "") if asset else "",
    }


def install_update(info, progress=None, status=None):
    """Download to a sibling file, verify SHA-256, then atomically install."""
    target = _install_target()
    if not info.get("available"):
        raise RuntimeError("Không có bản Launcher mới")
    digest = info.get("digest", "")
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise RuntimeError("Bản phát hành thiếu checksum SHA-256 để xác minh")
    url = info.get("asset_url", "")
    if not url.startswith(RELEASE_DOWNLOAD_PREFIX):
        raise RuntimeError("Đường dẫn tải AppImage không hợp lệ")
    expected_size = int(info.get("asset_size") or 0)
    if expected_size > MAX_DOWNLOAD_SIZE:
        raise RuntimeError("Bản cập nhật vượt quá giới hạn dung lượng")

    os.makedirs(os.path.dirname(target), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".wuwavh-update-", suffix=".AppImage", dir=os.path.dirname(target))
    os.close(fd)
    try:
        downloader.download_file(
            url, temporary, progress, strict_partial_fallback=True, engine_cb=status
        )

        if os.path.getsize(temporary) > MAX_DOWNLOAD_SIZE:
            raise RuntimeError("Bản cập nhật vượt quá giới hạn dung lượng")
        checksum = hashlib.sha256()
        with open(temporary, "rb") as downloaded_file:
            while chunk := downloaded_file.read(1024 * 1024):
                checksum.update(chunk)
        if checksum.hexdigest().lower() != digest.split(":", 1)[1].lower():
            raise RuntimeError("Checksum AppImage không khớp; bản cũ vẫn được giữ nguyên")
        with open(temporary, "rb") as downloaded_file:
            if downloaded_file.read(4) != b"\x7fELF":
                raise RuntimeError("File tải về không phải AppImage hợp lệ")
        permissions = stat.S_IMODE(os.stat(target).st_mode) if os.path.isfile(target) else 0o755
        os.chmod(temporary, permissions | stat.S_IXUSR)
        os.replace(temporary, target)
        return target
    finally:
        for leftover in (temporary, temporary + ".tmp", temporary + ".tmp.aria2"):
            if os.path.exists(leftover):
                os.unlink(leftover)

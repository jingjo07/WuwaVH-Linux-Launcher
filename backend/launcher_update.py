"""Check GitHub releases and safely replace the running AppImage."""

import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.request

from backend.version import LAUNCHER_VERSION


RELEASE_API = "https://api.github.com/repos/jingjo07/WuwaVH-Linux-Launcher/releases/latest"
ASSET_NAME = "WuWaVH-Launcher-x86_64.AppImage"
MAX_DOWNLOAD_SIZE = 300 * 1024 * 1024


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
    appimage = os.path.realpath(os.environ.get("APPIMAGE", ""))
    can_install = bool(
        newer and asset and os.path.isfile(appimage)
        and os.access(os.path.dirname(appimage), os.W_OK)
        and re.fullmatch(r"sha256:[a-fA-F0-9]{64}", asset.get("digest", ""))
        and asset.get("browser_download_url", "").startswith(
            "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/"
        )
    )
    return {
        "current_version": LAUNCHER_VERSION,
        "latest_version": tag.lstrip("vV"),
        "available": newer,
        "can_install": can_install,
        "release_url": release.get("html_url", ""),
        "asset_url": asset.get("browser_download_url", "") if asset else "",
        "digest": asset.get("digest", "") if asset else "",
    }


def install_update(info, progress=None):
    """Download to a sibling file, verify SHA-256, then atomically replace AppImage."""
    target = os.path.realpath(os.environ.get("APPIMAGE", ""))
    if not target or not os.path.isfile(target):
        raise RuntimeError("Tự cập nhật chỉ hỗ trợ khi chạy bằng AppImage")
    if not info.get("available"):
        raise RuntimeError("Không có bản Launcher mới")
    digest = info.get("digest", "")
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise RuntimeError("Bản phát hành thiếu checksum SHA-256 để xác minh")
    url = info.get("asset_url", "")
    if not url.startswith("https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/"):
        raise RuntimeError("Đường dẫn tải AppImage không hợp lệ")

    fd, temporary = tempfile.mkstemp(prefix=".wuwavh-update-", suffix=".AppImage", dir=os.path.dirname(target))
    try:
        downloaded = 0
        checksum = hashlib.sha256()
        request = urllib.request.Request(url, headers={"User-Agent": "WuWaVH-Launcher"})
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length", 0))
            if total > MAX_DOWNLOAD_SIZE:
                raise RuntimeError("Bản cập nhật vượt quá giới hạn dung lượng")
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_SIZE:
                    raise RuntimeError("Bản cập nhật vượt quá giới hạn dung lượng")
                output.write(chunk)
                checksum.update(chunk)
                if progress:
                    progress(downloaded, total)
            output.flush()
            os.fsync(output.fileno())
        if checksum.hexdigest().lower() != digest.split(":", 1)[1].lower():
            raise RuntimeError("Checksum AppImage không khớp; bản cũ vẫn được giữ nguyên")
        with open(temporary, "rb") as downloaded_file:
            if downloaded_file.read(4) != b"\x7fELF":
                raise RuntimeError("File tải về không phải AppImage hợp lệ")
        os.chmod(temporary, os.stat(target).st_mode | stat.S_IXUSR)
        os.replace(temporary, target)
        return target
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

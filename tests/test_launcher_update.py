import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from backend import launcher_update


class DownloadResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


class LauncherUpdateTests(unittest.TestCase):
    def test_version_comparison_ignores_trailing_zeroes(self):
        self.assertFalse(launcher_update._is_newer("v1.3.0", "1.3"))
        self.assertTrue(launcher_update._is_newer("v1.4", "1.3"))

    def test_check_update_detects_new_release_with_matching_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "Launcher.AppImage")
            with open(target, "wb") as output:
                output.write(b"old version")
            release = {
                "tag_name": "v9.9",
                "html_url": "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/tag/v9.9",
                "assets": [{
                    "name": launcher_update.ASSET_NAME,
                    "digest": "sha256:" + "a" * 64,
                    "browser_download_url": "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/v9.9/WuWaVH-Launcher-x86_64.AppImage",
                }],
            }
            with mock.patch.dict(os.environ, {"APPIMAGE": target}), mock.patch.object(
                launcher_update.urllib.request, "urlopen", return_value=DownloadResponse(json.dumps(release).encode())
            ):
                result = launcher_update.check_update()
            self.assertTrue(result["available"])
            self.assertTrue(result["can_install"])
            self.assertEqual(result["latest_version"], "9.9")

    def test_install_replaces_only_verified_appimage(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "Launcher.AppImage")
            with open(target, "wb") as output:
                output.write(b"old version")
            payload = b"\x7fELF" + b"new version"
            info = {
                "available": True,
                "asset_url": "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/v1.4/WuWaVH-Launcher-x86_64.AppImage",
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
            with mock.patch.dict(os.environ, {"APPIMAGE": target}), mock.patch.object(
                launcher_update.urllib.request, "urlopen", return_value=DownloadResponse(payload)
            ):
                self.assertEqual(launcher_update.install_update(info), target)
            with open(target, "rb") as updated:
                self.assertEqual(updated.read(), payload)

    def test_bad_checksum_preserves_existing_appimage(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "Launcher.AppImage")
            with open(target, "wb") as output:
                output.write(b"old version")
            info = {
                "available": True,
                "asset_url": "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/v1.4/WuWaVH-Launcher-x86_64.AppImage",
                "digest": "sha256:" + "0" * 64,
            }
            with mock.patch.dict(os.environ, {"APPIMAGE": target}), mock.patch.object(
                launcher_update.urllib.request, "urlopen", return_value=DownloadResponse(b"\x7fELFwrong")
            ):
                with self.assertRaisesRegex(RuntimeError, "Checksum"):
                    launcher_update.install_update(info)
            with open(target, "rb") as current:
                self.assertEqual(current.read(), b"old version")


if __name__ == "__main__":
    unittest.main()

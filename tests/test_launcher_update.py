import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from backend import downloader, launcher_update


ASSET_URL = (
    "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/download/"
    "v9.9/WuWaVH-Launcher-x86_64.AppImage"
)


class Response(io.BytesIO):
    def __init__(self, payload, status=200, headers=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {"Content-Length": str(len(payload))}

    def geturl(self):
        return ASSET_URL


def release_info(payload):
    return {
        "tag_name": "v9.9",
        "html_url": "https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases/tag/v9.9",
        "assets": [{
            "name": launcher_update.ASSET_NAME,
            "browser_download_url": ASSET_URL,
            "size": len(payload),
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        }],
    }


class LauncherUpdateTests(unittest.TestCase):
    def test_version_comparison_ignores_trailing_zeroes(self):
        self.assertFalse(launcher_update._is_newer("v1.3.0", "1.3"))
        self.assertTrue(launcher_update._is_newer("v1.4", "1.3"))

    def test_check_update_offers_install_from_source(self):
        payload = b"\x7fELFnew"
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"APPIMAGE": "", "XDG_DATA_HOME": directory}
        ), mock.patch.object(
            launcher_update.urllib.request, "urlopen",
            return_value=Response(json.dumps(release_info(payload)).encode()),
        ):
            info = launcher_update.check_update()
        self.assertTrue(info["available"])
        self.assertTrue(info["can_install"])
        self.assertEqual(info["asset_size"], len(payload))

    def test_install_uses_shared_download_pipeline_and_verifies_hash(self):
        payload = b"\x7fELFnew version"
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"APPIMAGE": "", "XDG_DATA_HOME": directory}
        ), mock.patch.object(downloader, "download_file") as download:
            def write_download(url, destination, progress, **options):
                with open(destination, "wb") as output:
                    output.write(payload)

            download.side_effect = write_download
            info = {
                "available": True,
                "asset_url": ASSET_URL,
                "asset_size": len(payload),
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
            target = launcher_update.install_update(info)
            self.assertEqual(target, os.path.join(directory, "wuwavh", launcher_update.ASSET_NAME))
            self.assertTrue(os.access(target, os.X_OK))
            with open(target, "rb") as installed:
                self.assertEqual(installed.read(), payload)
            self.assertTrue(download.call_args.kwargs["strict_partial_fallback"])

    def test_bad_checksum_keeps_old_appimage(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "Launcher.AppImage")
            with open(target, "wb") as output:
                output.write(b"old version")
            info = {
                "available": True,
                "asset_url": ASSET_URL,
                "asset_size": 8,
                "digest": "sha256:" + "0" * 64,
            }

            def write_download(url, destination, progress, **options):
                with open(destination, "wb") as output:
                    output.write(b"\x7fELFbad")

            with mock.patch.dict(os.environ, {"APPIMAGE": target}), mock.patch.object(
                downloader, "download_file", side_effect=write_download
            ):
                with self.assertRaisesRegex(RuntimeError, "Checksum"):
                    launcher_update.install_update(info)
            with open(target, "rb") as current:
                self.assertEqual(current.read(), b"old version")

    def test_read_only_appimage_uses_managed_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            current = os.path.join(directory, "old.AppImage")
            with open(current, "wb") as output:
                output.write(b"old version")
            with mock.patch.dict(os.environ, {"APPIMAGE": current, "XDG_DATA_HOME": directory}), mock.patch.object(
                launcher_update.os, "access", return_value=False
            ):
                target = launcher_update._install_target()
            self.assertEqual(target, os.path.join(directory, "wuwavh", launcher_update.ASSET_NAME))

    def test_shared_downloader_does_not_switch_after_aria2_partial_failure(self):
        probe = Response(b"x", status=206, headers={"Content-Range": "bytes 0-0/4194304"})
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "download.AppImage")

            def fail_after_writing(url, destination, size, headers, progress):
                with open(destination, "wb") as output:
                    output.write(b"partial")
                raise RuntimeError("connection lost")

            with mock.patch.object(downloader, "HAS_URLLIB3", False), mock.patch.object(
                downloader.urllib.request, "urlopen", return_value=probe
            ), mock.patch.object(downloader, "_find_aria2", return_value="aria2c"), mock.patch.object(
                downloader, "_download_aria2", side_effect=fail_after_writing
            ), mock.patch.object(downloader, "_download_dynamic_chunks") as dynamic:
                with self.assertRaisesRegex(RuntimeError, "aria2c bị gián đoạn"):
                    downloader.download_file(ASSET_URL, target, strict_partial_fallback=True)
            dynamic.assert_not_called()
            self.assertFalse(os.path.exists(target))

    def test_shared_downloader_can_fallback_before_first_byte(self):
        probe = Response(b"x", status=206, headers={"Content-Range": "bytes 0-0/4194304"})
        payload = b"\x7fELFdownloaded"
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "download.AppImage")

            def write_dynamic(url, destination, size, workers, chunk_size, headers, progress):
                with open(destination, "wb") as output:
                    output.write(payload)

            engines = []
            with mock.patch.object(downloader, "HAS_URLLIB3", False), mock.patch.object(
                downloader.urllib.request, "urlopen", return_value=probe
            ), mock.patch.object(downloader, "_find_aria2", return_value="aria2c"), mock.patch.object(
                downloader, "_download_aria2", side_effect=RuntimeError("failed before data")
            ), mock.patch.object(downloader, "_download_dynamic_chunks", side_effect=write_dynamic):
                downloader.download_file(ASSET_URL, target, strict_partial_fallback=True, engine_cb=engines.append)
            self.assertEqual(engines, ["aria2c", "dynamic"])
            with open(target, "rb") as downloaded:
                self.assertEqual(downloaded.read(), payload)

    def test_dynamic_failure_after_partial_download_does_not_restart_single_stream(self):
        probe = Response(b"x", status=206, headers={"Content-Range": "bytes 0-0/4194304"})
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "download.AppImage")

            def fail_after_writing(url, destination, size, workers, chunk_size, headers, progress):
                with open(destination, "wb") as output:
                    output.write(b"partial")
                raise RuntimeError("connection lost")

            with mock.patch.object(downloader, "HAS_URLLIB3", False), mock.patch.object(
                downloader.urllib.request, "urlopen", return_value=probe
            ) as urlopen, mock.patch.object(downloader, "_find_aria2", return_value=None), mock.patch.object(
                downloader, "_download_dynamic_chunks", side_effect=fail_after_writing
            ):
                with self.assertRaisesRegex(RuntimeError, "Bộ tải nhiều luồng bị gián đoạn"):
                    downloader.download_file(ASSET_URL, target, strict_partial_fallback=True)
            urlopen.assert_called_once()
            self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()

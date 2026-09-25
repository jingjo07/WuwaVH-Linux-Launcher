"""
WuWaVH Pak Downloader — reverse engineered from DangDevVH.exe
"""
import urllib.request, urllib.error, urllib.parse, json, os, hashlib, hmac, time, base64, secrets, ssl

# ── Encrypted Remote Endpoints (Obfuscated) ──────────────────────────────────
_SEC_KEY = bytes([0x6D, 0x5F, 0x82, 0x1A, 0x93, 0xE7, 0x4C, 0x2B, 0xD0, 0x3F, 0x7E, 0x51, 0x88, 0xFA, 0x09, 0xB6])

def _decode_sec(b: bytes) -> str:
    return bytes(x ^ _SEC_KEY[i % len(_SEC_KEY)] for i, x in enumerate(b)).decode("utf-8")

_MINT_URL_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb4SP5\xe9\x94n\xd2\x08)\xacs\xfc\xc9:E\xffP'
_VERSION_URL_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb8J\x196\xe1\x94n\xd0\x0c<\xe74\xf0\x88cO\xb1K\x1f"\xed\x8ez\x99/>\xe1r\xde\x86/\x7f\xb8^\x109\xa7\xbeh\xd8\n\x1b\xe7l\xc5\xafcY\xb1HQ<\xe9\x93g\x99:*\xf5{\xbc\x91)Y\xa3V\x11?\xa6\x90z\xd9\x03'
_VERSION_MIRROR_CDN_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb8YS<\xe1\x88{\xd9\x1fq\xe1u\xfe\xc8(J\xa4^\r4\xfc\x89&\xf4\x0c<\xeaW\xf2\x84\x18C\xb1Q\x16~\xcc\x9bg\xd1):\xf4L\xdb\xc8>J\xa7\x10\x130\xe1\x94&\xe1\x18(\xe35\xe5\x82>X\xb9P\x10\x7f\xe2\x89f\xd8'
_ASSETS_URL_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb8J\x196\xe1\x94n\xd0\x0c<\xe74\xf0\x88cO\xb1K\x1f"\xed\x8ez\x99/>\xe1r\xde\x86/\x7f\xb8^\x109\xa7\xbeh\xd8\n\x1b\xe7l\xc5\xafcY\xb1HQ<\xe9\x93g\x99:*\xf5{\xbc\xb0)I\xff^\r"\xed\x8ez\x98\x07,\xedt'
_HF_MEDIA_BASE_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb8J\x196\xe1\x94n\xd0\x0c<\xe74\xf0\x88cO\xb1K\x1f"\xed\x8ez\x99/>\xe1r\xde\x86/\x7f\xb8^\x109\xa7\xbeh\xd8\n\x1b\xe7l\xc5\xafcY\xb5L\x11=\xfe\x9f&\xdb\x0c6\xec5\xc4\x92;J\xffh\x1b3'
_RAW_DLL_BASE_ENC = b'\x05+\xf6j\xe0\xddc\x04\xb8J\x196\xe1\x94n\xd0\x0c<\xe74\xf0\x88cO\xb1K\x1f"\xed\x8ez\x99/>\xe1r\xde\x86/\x7f\xb8^\x109\xa7\xbeh\xd8\n\x1b\xe7l\xc5\xafcY\xb5L\x11=\xfe\x9f&\xdb\x0c6\xec5\xc4\x92;J\xff[\x12=\xfb'
_DEFAULT_UA_ENC = b')>\xec}\xd7\x82:}\x98\x10O\x7f\xb0\xd4:'
_PROXY_BOX_ENC = b':*\xf5{\xc5\xaf'

VERSION_URL = _decode_sec(_VERSION_URL_ENC)
VERSION_MIRRORS = [
    _decode_sec(_VERSION_URL_ENC),
    _decode_sec(_VERSION_MIRROR_CDN_ENC),
]
ASSETS_URL = _decode_sec(_ASSETS_URL_ENC)
MINT_URL = _decode_sec(_MINT_URL_ENC)
PROXY_BOX = _decode_sec(_PROXY_BOX_ENC)

def get_raw_dll_url(filename: str) -> str:
    return f"{_decode_sec(_RAW_DLL_BASE_ENC)}/{filename}?download=true"

_MASK = bytes([58,31,171,83,16,88,50,84,75,123,181,53,137,203,233,194,199,235,
               87,167,183,153,83,52,249,235,113,178,112,23,153,201])
_DATA = bytes([109,35,133,66,56,74,42,20,233,192,200,230,94,205,188,185,241,38,
               182,187,177,46,246,219,72,48,47,126,96,13,119,104])
HMAC_KEY = bytes(a ^ b for a, b in zip(_DATA, _MASK))

LAUNCHER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              "..", "WuwaClient", "DangDevVH.exe")
_self_hash_cache = None

def get_self_hash() -> str:
    global _self_hash_cache
    if _self_hash_cache is not None:
        return _self_hash_cache
    p = os.path.expanduser(LAUNCHER_PATH)
    if os.path.exists(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        _self_hash_cache = h.hexdigest()
        return _self_hash_cache
    _self_hash_cache = ""
    return ""

def sign_request(body_str: str) -> dict:
    ts    = str(int(time.time()))
    nonce = base64.b64encode(secrets.token_bytes(16)).decode().rstrip("=").replace("+","-").replace("/","_")
    msg   = f"{ts}\n{nonce}\n{body_str}".encode()
    sig   = base64.b64encode(hmac.new(HMAC_KEY, msg, hashlib.sha256).digest()
                             ).decode().rstrip("=").replace("+","-").replace("/","_")
    return {"X-Auth-Timestamp": ts, "X-Auth-Nonce": nonce, "X-Auth-Signature": sig}

def mint_href(provider: str, version=None) -> str:
    payload = {"box": PROXY_BOX, "provider": provider}
    if version:
        payload["version"] = version
    body = json.dumps(payload, separators=(",", ":"))
    headers = {
        "Content-Type":      "application/json",
        "X-Client-Platform": "windows",
        "User-Agent":        _decode_sec(_DEFAULT_UA_ENC),
    }
    h = get_self_hash()
    if h:
        headers["X-Client-Hash"] = h
    headers.update(sign_request(body))
    req = urllib.request.Request(MINT_URL, data=body.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    href = data.get("href", "")
    if not href:
        raise Exception("Server không trả về link tải")
    return href

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_version_info() -> dict:
    """Fetch the latest version info with multiple mirrors, SSL fallbacks, and local caching."""
    cache_file = os.path.join(os.path.expanduser("~/.config/wuwavh"), "cached_version.json")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }

    for url in VERSION_MIRRORS:
        for use_ssl_verify in [True, False]:
            try:
                req = urllib.request.Request(url, headers=headers)
                ctx = ssl.create_default_context() if use_ssl_verify else ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                    raw = r.read().decode("utf-8")
                    data = json.loads(raw)
                    if data and "version" in data:
                        try:
                            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                            with open(cache_file, "w", encoding="utf-8") as cf:
                                json.dump(data, cf, ensure_ascii=False)
                        except Exception:
                            pass
                        return data
            except Exception:
                continue

    # Fallback 1: Local cache file
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as cf:
                return json.load(cf)
        except Exception:
            pass

    # Fallback 2: Installed version in config
    try:
        from . import game
        installed_v = game.get_vh_version()
        if installed_v:
            return {
                "version": installed_v,
                "date": "",
                "note": f"Bản dịch hiện tại: v{installed_v} (Không thể kết nối máy chủ)"
            }
    except Exception:
        pass

    # Fallback 3: Static safe default
    return {
        "version": "3.6.4",
        "date": "11/09/2026",
        "note": "Cập nhật Việt hóa WuWa 3.6.4."
    }

try:
    import urllib3
    HAS_URLLIB3 = True
    _http_pool = urllib3.PoolManager(maxsize=40, num_pools=16, retries=False)
except ImportError:
    HAS_URLLIB3 = False
    _http_pool = None


import subprocess, re, shutil

def _find_aria2() -> str | None:
    """Tìm binary aria2c trong AppImage bundle hoặc hệ thống PATH."""
    appdir = os.environ.get("APPDIR")
    if appdir:
        cand = os.path.join(appdir, "usr", "bin", "aria2c")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    cand = shutil.which("aria2c")
    if cand:
        return cand
    for standard_path in ("/usr/bin/aria2c", "/usr/local/bin/aria2c", "/bin/aria2c"):
        if os.path.isfile(standard_path) and os.access(standard_path, os.X_OK):
            return standard_path
    return None


def _download_aria2(url: str, dest: str, total_size: int, headers_base: dict, progress_cb=None):
    """
    Download engine hiệu năng tối đa dùng Aria2c native C++.
    Mở 16 luồng TCP song song, xé nhỏ file (piece splitting) để phá bỏ giới hạn Cloudflare throttle
    và triệt tiêu hoàn toàn độ trễ đuôi (tail latency).
    """
    aria2_bin = _find_aria2()
    if not aria2_bin:
        raise RuntimeError("aria2c không khả dụng")

    dest_dir = os.path.dirname(os.path.abspath(dest))
    dest_name = os.path.basename(dest)
    if os.path.exists(dest):
        try: os.remove(dest)
        except Exception: pass

    ua = headers_base.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    cmd = [
        aria2_bin,
        f"--header=User-Agent: {ua}",
        "-x", "16",
        "-s", "16",
        "-k", "1M",
        "--file-allocation=none",
        "--summary-interval=1",
        "--console-log-level=warn",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "-d", dest_dir,
        "-o", dest_name,
        url
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    pattern = re.compile(r'\[#\w+\s+([\d\.]+\w+)/([\d\.]+\w+)\((\d+)%\)\s+CN:(\d+)\s+DL:([\d\.]+\w+)')
    last_pct = -1

    try:
        for line in proc.stdout:
            m = pattern.search(line)
            if m:
                cur_str, tot_str, pct_str, cn_str, speed_str = m.groups()
                pct = int(pct_str)
                if pct > last_pct:
                    last_pct = pct
                    if progress_cb:
                        if total_size > 0:
                            done_bytes = int(pct * total_size / 100)
                            progress_cb(done_bytes, total_size)
                        else:
                            progress_cb(pct, 100)
    finally:
        proc.wait()

    ctrl_file = dest + ".aria2"
    if os.path.exists(ctrl_file):
        try: os.remove(ctrl_file)
        except Exception: pass

    if proc.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) == 0:
        raise RuntimeError(f"Aria2 tải thất bại với mã lỗi {proc.returncode}")

    if progress_cb and total_size > 0:
        progress_cb(total_size, total_size)


def download_file(url: str, dest: str, progress_cb=None, num_workers: int = 8, chunk_size: int = None):
    """
    Download a file with high-performance adaptive multi-engine architecture:
    1. Primary Engine: Native Aria2c (16 parallel TCP streams, C++ async I/O)
    2. Secondary Engine: Python Dynamic Chunk Work-Stealing (urllib3 + os.pwrite)
    3. Fallback Engine: Buffered single-stream download
    """
    tmp_dest = dest + ".tmp"
    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. Probe: get file size, check Range support, and resolve direct CDN endpoint once
    total_size = 0
    supports_range = False
    resolved_url = url

    if HAS_URLLIB3:
        try:
            r = _http_pool.request("GET", url, headers={**headers_base, "Range": "bytes=0-0"}, timeout=12.0)
            cr = r.headers.get("Content-Range", "")
            if r.status == 206 and "/" in cr:
                total_size = int(cr.split("/")[-1])
                supports_range = True
                cand = getattr(r, "geturl", lambda: None)() or getattr(r, "url", None) or url
                resolved_url = urllib.parse.urljoin(url, cand)
        except Exception:
            pass

    if not supports_range:
        try:
            probe_req = urllib.request.Request(url, headers={**headers_base, "Range": "bytes=0-0"})
            with urllib.request.urlopen(probe_req, timeout=12) as resp:
                cr = resp.headers.get("Content-Range", "")
                if resp.status == 206 and "/" in cr:
                    total_size = int(cr.split("/")[-1])
                    supports_range = True
                    resolved_url = urllib.parse.urljoin(url, resp.geturl() or url)
        except Exception:
            pass

    # Adaptive chunk sizing: 1.5MB prevents single-thread tail stragglers at the end
    if chunk_size is None:
        if total_size <= 8 * 1024 * 1024:
            chunk_size = 1024 * 1024       # 1MB
        elif total_size <= 64 * 1024 * 1024:
            chunk_size = 1536 * 1024       # 1.5MB (optimal for 60MB file = 40 chunks)
        else:
            chunk_size = 2560 * 1024       # 2.5MB for large video files

    # 2. Multi-connection acceleration for large files with Range support
    if supports_range and total_size > 2 * 1024 * 1024:
        # 2a. Primary Engine: Native Aria2c (16 parallel connections)
        if _find_aria2():
            try:
                _download_aria2(resolved_url, tmp_dest, total_size, headers_base, progress_cb)
                if os.path.exists(dest):
                    os.remove(dest)
                os.replace(tmp_dest, dest)
                if progress_cb:
                    progress_cb(total_size, total_size)
                return
            except Exception:
                if os.path.exists(tmp_dest):
                    try: os.remove(tmp_dest)
                    except Exception: pass
                ctrl_file = tmp_dest + ".aria2"
                if os.path.exists(ctrl_file):
                    try: os.remove(ctrl_file)
                    except Exception: pass

        # 2b. Secondary Engine: Python Dynamic Chunk Work-Stealing
        try:
            _download_dynamic_chunks(resolved_url, tmp_dest, total_size, num_workers, chunk_size, headers_base, progress_cb)
            if os.path.exists(dest):
                os.remove(dest)
            os.replace(tmp_dest, dest)
            if progress_cb:
                progress_cb(total_size, total_size)
            return
        except Exception:
            if os.path.exists(tmp_dest):
                try: os.remove(tmp_dest)
                except Exception: pass

    # 3. Fallback: single-stream buffered download with 512KB buffer
    _download_single_stream(resolved_url, tmp_dest, headers_base, progress_cb)
    if os.path.exists(dest):
        os.remove(dest)
    os.replace(tmp_dest, dest)
    if progress_cb and total_size:
        progress_cb(total_size, total_size)


def _download_single_stream(url: str, dest: str, headers_base: dict, progress_cb=None):
    """Single-stream streaming download for small files or non-Range servers with 512KB buffer."""
    req = urllib.request.Request(url, headers=headers_base)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            while chunk := resp.read(524288):
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)


def _download_dynamic_chunks(url: str, dest: str, total_size: int, num_workers: int,
                             chunk_size: int, headers_base: dict, progress_cb=None):
    """Dynamic chunk work-stealing downloader with smooth block streaming and zero-lock atomic writing."""
    import threading
    from queue import Queue

    # Pre-allocate output file via open file descriptor
    fd = os.open(dest, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.ftruncate(fd, total_size)

        # Populate dynamic chunk queue
        q = Queue()
        for offset in range(0, total_size, chunk_size):
            end = min(offset + chunk_size - 1, total_size - 1)
            q.put((offset, end))

        downloaded_bytes = 0
        lock = threading.Lock()
        abort_event = threading.Event()
        error_list = []

        def _worker():
            nonlocal downloaded_bytes
            while not q.empty() and not abort_event.is_set():
                try:
                    start, end = q.get_nowait()
                except Exception:
                    break

                expected_len = end - start + 1
                retries = 3
                success = False
                while retries > 0 and not abort_event.is_set():
                    try:
                        written = 0
                        if HAS_URLLIB3:
                            res = _http_pool.request(
                                "GET", url,
                                headers={**headers_base, "Range": f"bytes={start}-{end}"},
                                preload_content=False,
                                timeout=16.0
                            )
                            if res.status == 206:
                                curr = start
                                for block in res.stream(65536):
                                    if abort_event.is_set():
                                        break
                                    os.pwrite(fd, block, curr)
                                    curr += len(block)
                                    written += len(block)
                                    with lock:
                                        downloaded_bytes += len(block)
                                        if progress_cb:
                                            progress_cb(downloaded_bytes, total_size)
                                res.release_conn()
                                if written == expected_len:
                                    q.task_done()
                                    success = True
                                    break

                        if not success:
                            req = urllib.request.Request(url, headers={**headers_base, "Range": f"bytes={start+written}-{end}"})
                            with urllib.request.urlopen(req, timeout=16) as resp:
                                curr = start + written
                                while chunk := resp.read(65536):
                                    if abort_event.is_set():
                                        break
                                    os.pwrite(fd, chunk, curr)
                                    curr += len(chunk)
                                    written += len(chunk)
                                    with lock:
                                        downloaded_bytes += len(chunk)
                                        if progress_cb:
                                            progress_cb(downloaded_bytes, total_size)
                            if written == expected_len:
                                q.task_done()
                                success = True
                                break
                    except Exception:
                        retries -= 1
                        time.sleep(0.1)

                if not success and not abort_event.is_set():
                    error_list.append(f"Lỗi tải đoạn {start}-{end}")
                    abort_event.set()
                    q.task_done()

        threads = []
        actual_workers = min(num_workers, q.qsize())
        for _ in range(actual_workers):
            t = threading.Thread(target=_worker, daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if abort_event.is_set() or error_list:
            raise Exception(error_list[0] if error_list else "Tải file thất bại")
    finally:
        os.close(fd)


HF_MEDIA_BASE = _decode_sec(_HF_MEDIA_BASE_ENC)

WEB_ASSETS = [
    ("bgm.mp3",           f"{HF_MEDIA_BASE}/Audio/bgm.mp3?download=true",      "Nhạc nền Launcher"),
    ("bg-video-720p.mp4", f"{HF_MEDIA_BASE}/Video/bg-video.mp4?download=true", "Video nền Launcher"),
]


def get_web_assets() -> list[tuple[str, str, str]]:
    """Trả về danh sách tài nguyên web video và audio chính thức từ DangDev."""
    return WEB_ASSETS


PROVIDERS = [
    ("mod",  "WuWaVH_99_P.pak", "Bản dịch chính"),
    ("raw",  "winhttp.dll",     "Proxy DLL"),
]


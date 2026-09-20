"""
Game process management for WuWaVH Launcher
"""
import os, subprocess, json, glob, shutil, time, re
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ── Cache Infrastructure ─────────────────────────────────────────────────────
_cache = {
    "config": None,
    "config_mtime": 0,
    "game_path": None,
    "game_path_ts": 0,
    "launcher_info": None,
    "launcher_info_ts": 0,
}
_CACHE_TTL = 30  # seconds — recalculate heavy lookups every 30s at most

CONFIG_PATH = os.path.expanduser("~/.config/wuwavh/config.json")
GAME_EXE_NAME = "Client-Win64-Shipping.exe"
PAK_SUBPATH   = "Client/Binaries/Win64/wuwaVietHoa"

def get_bundled_paks_dir() -> str:
    """Return bundled/read-only paks directory (inside AppImage or local root)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paks")

def get_paks_dir() -> str:
    """Return writable paks directory for downloading/building new PAKs."""
    candidate = get_bundled_paks_dir()
    if os.environ.get("APPDIR") or os.environ.get("APPIMAGE") or not os.access(candidate, os.W_OK):
        user_paks = os.path.expanduser("~/.config/wuwavh/paks")
        os.makedirs(user_paks, exist_ok=True)
        return user_paks
    os.makedirs(candidate, exist_ok=True)
    return candidate

DEFAULT_SEARCH_PATHS = [
    "~/.steam/steam/steamapps/common/Wuthering Waves",
    "~/Games/Wuthering Waves",
    "~/.local/share/Steam/steamapps/common/Wuthering Waves",
    "/opt/wuthering-waves",
]

def load_config() -> dict:
    """Load config with file-mtime cache to avoid redundant disk reads."""
    try:
        mtime = os.path.getmtime(CONFIG_PATH) if os.path.exists(CONFIG_PATH) else 0
    except OSError:
        mtime = 0
    if _cache["config"] is not None and mtime == _cache["config_mtime"]:
        return _cache["config"]
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            _cache["config"] = cfg
            _cache["config_mtime"] = mtime
            return cfg
        except Exception:
            pass
    return {}

def _invalidate_config_cache():
    """Call after saving config to force re-read on next load_config()."""
    _cache["config"] = None
    _cache["config_mtime"] = 0
    _cache["game_path"] = None
    _cache["game_path_ts"] = 0
    _cache["launcher_info"] = None
    _cache["launcher_info_ts"] = 0

def save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    _invalidate_config_cache()

def detect_game_path() -> str | None:
    """Try to auto-detect Wuthering Waves installation path (cached for 30s)."""
    now = time.monotonic()
    if _cache["game_path"] is not None and (now - _cache["game_path_ts"]) < _CACHE_TTL:
        return _cache["game_path"]

    result = _detect_game_path_uncached()
    _cache["game_path"] = result
    _cache["game_path_ts"] = now
    return result

def _detect_game_path_uncached() -> str | None:
    """Actual game path detection (expensive: reads config, scans dirs)."""
    cfg = load_config()
    if cfg.get("game_path") and os.path.isdir(cfg["game_path"]):
        return cfg["game_path"]

    for p in DEFAULT_SEARCH_PATHS:
        expanded = os.path.expanduser(p)
        if os.path.isdir(expanded):
            return expanded

    # Try Steam library folders
    steam_lib_file = os.path.expanduser("~/.steam/steam/steamapps/libraryfolders.vdf")
    if os.path.exists(steam_lib_file):
        with open(steam_lib_file) as f:
            content = f.read()
        for line in content.splitlines():
            if '"path"' in line:
                path = line.split('"')[-2]
                candidate = os.path.join(path, "steamapps", "common", "Wuthering Waves")
                if os.path.isdir(candidate):
                    return candidate
    return None

def set_game_path(path: str):
    cfg = load_config()
    cfg["game_path"] = path
    save_config(cfg)

def get_pak_dir() -> str | None:
    game = detect_game_path()
    if game:
        return os.path.join(game, PAK_SUBPATH)
    return None

def get_game_exe() -> str | None:
    game_dir = detect_game_path()
    if not game_dir:
        return None
    # Fast path: check standard relative locations directly (instant stat, no recursive glob)
    for sub in [
        os.path.join("Client", "Binaries", "Win64", GAME_EXE_NAME),
        os.path.join("Wuthering Waves Game", "Client", "Binaries", "Win64", GAME_EXE_NAME),
    ]:
        candidate = os.path.join(game_dir, sub)
        if os.path.isfile(candidate):
            return candidate
    # Fallback: search recursively if custom non-standard folder layout
    matches = glob.glob(os.path.join(game_dir, "**", GAME_EXE_NAME), recursive=True)
    if matches:
        return matches[0]
    return None

def is_game_running() -> bool:
    """
    Kiểm tra xem game (Client-Win64-Shipping.exe / Wuthering Waves) có đang thực sự chạy không.
    Chỉ bắt đúng tiến trình game (Wine/Proton binary hoặc Windows exe),
    bỏ qua hoàn toàn các tiến trình wrapper (bash, sh, heroic, steam, python)
    và các tiến trình zombie/defunct.
    """
    GAME_NAMES = {
        "client-win64-sh",
        "client-win64-shipping.exe",
        "client-win64-shipping",
        "wutheringwaves.exe",
        "wutheringwaves",
    }
    WINE_PRELOADERS = {
        "wine64-preloader",
        "wine-preloader",
        "wine",
        "wine64",
    }
    IGNORED_PROCESS_NAMES = {
        "bash", "sh", "zsh", "python", "python3",
        "heroic", "steam", "steamwebhelper",
        "wineserver", "services.exe", "explorer.exe",
        "rpcss.exe", "conhost.exe", "svchost.exe",
        "plugplay.exe", "tabtip.exe", "gamemoded",
    }

    if HAS_PSUTIL:
        try:
            for p in psutil.process_iter(["name", "cmdline", "status"]):
                try:
                    # 1. Bỏ qua tiến trình đã chết / zombie
                    status = p.info.get("status")
                    if status in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                        continue

                    pname = (p.info.get("name") or "").lower()
                    if pname in IGNORED_PROCESS_NAMES:
                        continue

                    cmdline_list = p.info.get("cmdline") or []
                    pcmd = " ".join(cmdline_list).lower()

                    # 2. Khớp trực tiếp tên tiến trình game
                    if pname in GAME_NAMES:
                        return True

                    # 3. Nếu là tiến trình Wine/Proton runner, kiểm tra exe trong cmdline
                    if pname in WINE_PRELOADERS:
                        if any(gn in pcmd for gn in ["client-win64-shipping", "wutheringwaves"]):
                            return True

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    pass
        except Exception:
            pass
    else:
        # Lightweight pgrep fallback when psutil is not available
        try:
            res = subprocess.run(["pgrep", "-f", "Client-Win64-Shipping"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


STEAM_APP_ID = "3513350"

# ── Proton / Steam helpers (reserved for future Proton direct-launch) ────────
# Các hàm dưới đây được giữ lại để sau này hỗ trợ chạy game trực tiếp qua
# Proton mà không cần Steam GUI. Hiện tại launch_game() dùng steam -applaunch.

COMPAT_TOOL_NAME = "dwproton-11.0-4-x86_64"

# Nơi Steam lưu custom Proton (GE-Proton, dwproton, ...)
COMPAT_TOOLS_DIRS = [
    "~/.local/share/Steam/compatibilitytools.d",
    "~/.steam/steam/compatibilitytools.d",
]

# Proton cài sẵn trong steamapps (key = tên thư mục, value = tên hiển thị)
BUILTIN_PROTON_DIRS = [
    "~/.local/share/Steam/steamapps/common",
    "~/.steam/steam/steamapps/common",
]


def _find_proton_script() -> str | None:
    """
    Tìm đường dẫn tới script 'proton' dựa trên COMPAT_TOOL_NAME.
    Trả về path tới file 'proton' hoặc None nếu không tìm thấy.
    """
    tool_variants = [
        COMPAT_TOOL_NAME,
        COMPAT_TOOL_NAME.replace("-x86_64", ""),
        COMPAT_TOOL_NAME.replace("-amd64", ""),
    ]

    for base in COMPAT_TOOLS_DIRS:
        base_exp = os.path.expanduser(base)
        if not os.path.isdir(base_exp):
            continue
        for variant in tool_variants:
            candidate = os.path.join(base_exp, variant, "proton")
            if os.path.isfile(candidate):
                return candidate

    for base in BUILTIN_PROTON_DIRS:
        base_exp = os.path.expanduser(base)
        if not os.path.isdir(base_exp):
            continue
        for variant in tool_variants:
            candidate = os.path.join(base_exp, variant, "proton")
            if os.path.isfile(candidate):
                return candidate
        try:
            for entry in os.listdir(base_exp):
                if "proton" in entry.lower():
                    candidate = os.path.join(base_exp, entry, "proton")
                    if os.path.isfile(candidate):
                        return candidate
        except PermissionError:
            pass

    return None


def _find_steam_root() -> str | None:
    """Tìm thư mục gốc cài đặt Steam."""
    for c in ["~/.local/share/Steam", "~/.steam/steam", "~/.steam/root"]:
        exp = os.path.expanduser(c)
        if os.path.isdir(exp):
            return exp
    return None


def _find_compat_data_path() -> str | None:
    """Tìm compatdata prefix của game (STEAM_COMPAT_DATA_PATH)."""
    for c in [
        f"~/.local/share/Steam/steamapps/compatdata/{STEAM_APP_ID}",
        f"~/.steam/steam/steamapps/compatdata/{STEAM_APP_ID}",
    ]:
        exp = os.path.expanduser(c)
        if os.path.isdir(exp):
            return exp
    return None


def _is_steam_running() -> bool:
    """Kiểm tra Steam client có đang chạy không."""
    if HAS_PSUTIL:
        for p in psutil.process_iter(["name"]):
            try:
                name = p.info["name"] or ""
                if name.lower() in ("steam", "steam.exe", "steamwebhelper"):
                    return True
            except Exception:
                pass
    else:
        r = subprocess.run(["pgrep", "-x", "steam"], capture_output=True)
        return r.returncode == 0
    return False


def fix_steam_launch_options():
    """Sửa lỗi cú pháp WINEDLLOVERRIDES trong cấu hình Steam nếu bị dính .dll extension."""
    import glob
    vdf_files = glob.glob(os.path.expanduser('~/.local/share/Steam/userdata/*/config/localconfig.vdf')) + \
                glob.glob(os.path.expanduser('~/.steam/steam/userdata/*/config/localconfig.vdf'))
    for path in set(vdf_files):
        if not os.path.exists(path): continue
        try:
            with open(path, 'r', errors='ignore') as f:
                content = f.read()
            if 'winhttp.dll=n,b' in content:
                new_content = content.replace('winhttp.dll=n,b', 'winhttp=n,b')
                with open(path, 'w') as f:
                    f.write(new_content)
                print(f"[Steam Fix] Đã sửa WINEDLLOVERRIDES trong {path}")
        except Exception:
            pass


def detect_heroic_game() -> dict | None:
    """Tự động phát hiện Wuthering Waves trong Heroic Games Launcher."""
    heroic_config_paths = [
        os.path.expanduser("~/.config/heroic"),
        os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic"),
    ]
    for hcp in heroic_config_paths:
        if not os.path.exists(hcp):
            continue

        # 1. Kiểm tra Sideload apps (sideload_apps/library.json)
        sideload_file = os.path.join(hcp, "sideload_apps", "library.json")
        if os.path.exists(sideload_file):
            try:
                with open(sideload_file, "r") as f:
                    data = json.load(f)
                    for g in data.get("games", []):
                        title = str(g.get("title", "")).lower()
                        exe = str(g.get("install", {}).get("executable", "")).lower()
                        folder = str(g.get("folder_name", "")).lower()
                        if any(k in title or k in exe or k in folder for k in ("wuthering", "wuwa", "client-win64")):
                            return {
                                "runner": g.get("runner", "sideload"),
                                "app_name": g.get("app_name"),
                                "title": g.get("title", "Wuthering Waves"),
                            }
            except Exception:
                pass

        # 2. Kiểm tra Legendary (Epic Games)
        legendary_installed = os.path.join(hcp, "legendaryConfig", "legendary", "installed.json")
        if os.path.exists(legendary_installed):
            try:
                with open(legendary_installed, "r") as f:
                    data = json.load(f)
                    for app_name, info in data.items():
                        title = str(info.get("title", "")).lower()
                        if "wuthering" in title or "wuwa" in title:
                            return {
                                "runner": "epic",
                                "app_name": app_name,
                                "title": info.get("title", "Wuthering Waves"),
                            }
            except Exception:
                pass
    return None


def is_heroic_installed() -> bool:
    """Kiểm tra Heroic Games Launcher có tồn tại trên máy không."""
    if shutil.which("heroic"):
        return True
    for p in [
        "~/.config/heroic",
        "~/.var/app/com.heroicgameslauncher.hgl",
        "/usr/bin/heroic",
        "/usr/local/bin/heroic",
        "/opt/Heroic",
        "/opt/heroic",
        "~/.local/share/applications/heroic.desktop",
        "~/.local/share/applications/com.heroicgameslauncher.hgl.desktop",
        "/usr/share/applications/heroic.desktop",
        "/usr/share/applications/com.heroicgameslauncher.hgl.desktop",
    ]:
        if os.path.exists(os.path.expanduser(p)):
            return True
    return False


def is_steam_installed() -> bool:
    """Kiểm tra Steam có tồn tại trên máy không."""
    if shutil.which("steam"):
        return True
    for p in [
        "~/.local/share/Steam",
        "~/.steam/steam",
        "~/.steam/root",
        "~/.var/app/com.valvesoftware.Steam",
        "/usr/bin/steam",
        "/usr/share/applications/steam.desktop",
    ]:
        if os.path.exists(os.path.expanduser(p)):
            return True
    return False


def get_launcher_info() -> dict:
    """Trả về thông tin về các launcher khả dụng và launcher đang chọn (cached 30s)."""
    now = time.monotonic()
    if _cache["launcher_info"] is not None and (now - _cache["launcher_info_ts"]) < _CACHE_TTL:
        # Update 'current' preference from config (cheap) in case it changed
        cached = _cache["launcher_info"]
        cached["current"] = load_config().get("launcher", "steam")
        return cached

    result = _get_launcher_info_uncached()
    _cache["launcher_info"] = result
    _cache["launcher_info_ts"] = now
    return result

def _get_launcher_info_uncached() -> dict:
    """Actual launcher info detection (expensive: scans disk paths, Heroic configs)."""
    cfg = load_config()
    pref = cfg.get("launcher", "steam")
    steam_avail = is_steam_installed()
    heroic_avail = is_heroic_installed()
    heroic_game = detect_heroic_game()

    return {
        "current": pref,
        "steam_available": steam_avail,
        "heroic_available": heroic_avail,
        "heroic_has_game": heroic_game is not None,
        "heroic_game": heroic_game,
        "heroic": {
            "available": heroic_avail,
            "game_found": heroic_game is not None,
            "game_title": heroic_game.get("title") if heroic_game else None,
            "runner": heroic_game.get("runner") if heroic_game else None,
            "app_name": heroic_game.get("app_name") if heroic_game else None,
        },
        "steam": {
            "available": steam_avail,
        }
    }


def set_preferred_launcher(launcher_type: str) -> dict:
    """Lưu lựa chọn launcher (steam hoặc heroic)."""
    if launcher_type not in ("steam", "heroic"):
        raise ValueError("Launcher không hợp lệ (chỉ hỗ trợ 'steam' hoặc 'heroic')")
    cfg = load_config()
    cfg["launcher"] = launcher_type
    save_config(cfg)
    return get_launcher_info()


def get_required_dll_overrides() -> str:
    """
    Tự động phát hiện các DLL hook/mod trong thư mục Binaries/Win64/ của game
    để tạo chuỗi WINEDLLOVERRIDES chuẩn nhất (ví dụ: winhttp=n,b,dxgi=n,b).
    """
    overrides = ["winhttp=n,b"]
    game_path = detect_game_path()
    if game_path:
        bin_dir = os.path.join(game_path, "Client", "Binaries", "Win64")
        if os.path.isdir(bin_dir):
            for dll_name in ("dxgi", "d3d12", "d3d11", "version", "dinput8"):
                dll_file = os.path.join(bin_dir, f"{dll_name}.dll")
                if os.path.isfile(dll_file):
                    overrides.append(f"{dll_name}=n,b")
    return ",".join(dict.fromkeys(overrides))


def optimize_heroic_config():
    """
    Tối ưu cấu hình Heroic Games Launcher để ngăn ngừa crash Fatal Error:
    1. Bật hideWindowOnProtocolLaunch và minimizeOnLaunch
    2. Tắt enableWineWayland (driver Wine Wayland gây crash Fatal Error trong Unreal Engine 4)
    3. Đồng bộ tham số -dx11 (DirectX 11 mode / DXVK) vào launcherArgs (tránh crash VKD3D DX12)
    4. Bật autoInstallDxvk: true
    5. Cấu hình đúng WINEDLLOVERRIDES bao gồm cả winhttp=n,b và dxgi=n,b (OptiScaler/Mods)
    """
    heroic_config_roots = [
        os.path.expanduser("~/.config/heroic"),
        os.path.expanduser("~/.var/app/com.heroicgameslauncher.hgl/config/heroic"),
    ]
    use_dx11 = get_dx11_mode()
    use_csharp = get_csharp_env_mode()
    target_overrides = get_required_dll_overrides()

    for root in heroic_config_roots:
        if not os.path.exists(root):
            continue

        # 1. Bật hideWindowOnProtocolLaunch và minimizeOnLaunch trong config.json
        conf_path = os.path.join(root, "config.json")
        if os.path.exists(conf_path):
            try:
                with open(conf_path, "r") as f:
                    data = json.load(f)
                modified = False
                if "defaultSettings" in data:
                    if not data["defaultSettings"].get("hideWindowOnProtocolLaunch"):
                        data["defaultSettings"]["hideWindowOnProtocolLaunch"] = True
                        modified = True
                    if not data["defaultSettings"].get("minimizeOnLaunch"):
                        data["defaultSettings"]["minimizeOnLaunch"] = True
                        modified = True
                if modified:
                    with open(conf_path, "w") as f:
                        json.dump(data, f, indent=2)
                    print(f"[Heroic Config] Đã bật ẩn cửa sổ Heroic khi launch game trong {conf_path}")
            except Exception as e:
                print(f"[Heroic Config Warning] {e}")

        # 2. Cấu hình và sửa lỗi trong GamesConfig/*.json
        games_cfg_dir = os.path.join(root, "GamesConfig")
        if os.path.exists(games_cfg_dir):
            for conf_file in glob.glob(os.path.join(games_cfg_dir, "*.json")):
                try:
                    with open(conf_file, "r") as f:
                        data = json.load(f)

                    changed = False
                    for app_key, app_cfg in data.items():
                        if not isinstance(app_cfg, dict):
                            continue

                        # 2.1 Tắt enableWineWayland nếu đang bật (driver Wine Wayland gây crash Fatal Error trên UE4)
                        if app_cfg.get("enableWineWayland"):
                            app_cfg["enableWineWayland"] = False
                            changed = True
                            print(f"[Heroic Fix] Đã tắt enableWineWayland trong {conf_file} để chống Fatal Error")

                        # 2.2 Đảm bảo bật autoInstallDxvk
                        if not app_cfg.get("autoInstallDxvk", True):
                            app_cfg["autoInstallDxvk"] = True
                            changed = True

                        # 2.3 Đồng bộ -dx11 & -ForceEnableCSharpEnvironment trong launcherArgs
                        cur_args = app_cfg.get("launcherArgs", "")
                        args_list = cur_args.split() if cur_args else []

                        # DX11 toggle
                        if use_dx11:
                            if "-dx11" not in args_list and "-d3d11" not in args_list:
                                args_list.append("-dx11")
                                changed = True
                                print(f"[Heroic Fix] Đã thêm -dx11 vào launcherArgs trong {conf_file}")
                        else:
                            if "-dx11" in args_list:
                                args_list.remove("-dx11")
                                changed = True
                            if "-d3d11" in args_list:
                                args_list.remove("-d3d11")
                                changed = True

                        # CSharp Environment toggle
                        if use_csharp:
                            if "-ForceEnableCSharpEnvironment" not in args_list:
                                args_list.append("-ForceEnableCSharpEnvironment")
                                changed = True
                                print(f"[Heroic Fix] Đã thêm -ForceEnableCSharpEnvironment vào launcherArgs trong {conf_file}")
                        else:
                            if "-ForceEnableCSharpEnvironment" in args_list:
                                args_list.remove("-ForceEnableCSharpEnvironment")
                                changed = True

                        if changed:
                            app_cfg["launcherArgs"] = " ".join(args_list)

                        # 2.4 Đảm bảo WINEDLLOVERRIDES đầy đủ (winhttp=n,b, dxgi=n,b nếu có OptiScaler)
                        env_opts = app_cfg.get("enviromentOptions", [])
                        found_override = False
                        for opt in env_opts:
                            if opt.get("key") == "WINEDLLOVERRIDES":
                                found_override = True
                                if opt.get("value") != target_overrides:
                                    opt["value"] = target_overrides
                                    changed = True
                                    print(f"[Heroic Fix] Cập nhật WINEDLLOVERRIDES='{target_overrides}' trong {conf_file}")

                        if not found_override:
                            env_opts.append({"key": "WINEDLLOVERRIDES", "value": target_overrides})
                            app_cfg["enviromentOptions"] = env_opts
                            changed = True
                            print(f"[Heroic Fix] Đã thêm WINEDLLOVERRIDES='{target_overrides}' trong {conf_file}")

                    if changed:
                        with open(conf_file, "w") as f:
                            json.dump(data, f, indent=2)
                except Exception as e:
                    print(f"[Heroic Config Fix Error] {conf_file}: {e}")


def _inject_dll_overrides_into_reg(reg_path: str) -> bool:
    """Inject [Software\\Wine\\DllOverrides] entries into a Wine/Proton user.reg file."""
    if not os.path.isfile(reg_path):
        return False
    try:
        with open(reg_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        overrides = {
            '"winhttp"': '"native,builtin"',
            '"dxgi"': '"native,builtin"',
            '"d3d11"': '"native,builtin"',
            '"d3d12"': '"native,builtin"',
            '"version"': '"native,builtin"',
        }

        section_header = "[Software\\\\Wine\\\\DllOverrides]"
        if "Software\\Wine\\DllOverrides" in content or "Software\\\\Wine\\\\DllOverrides" in content:
            lines = content.splitlines()
            new_lines = []
            in_section = False
            added_keys = set()

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    if in_section:
                        for k, v in overrides.items():
                            if k not in added_keys:
                                new_lines.append(f"{k}={v}")
                        in_section = False
                    clean_hdr = stripped.lower().replace("\\\\", "\\")
                    if clean_hdr == "[software\\wine\\dlloverrides]":
                        in_section = True
                elif in_section:
                    for k in overrides:
                        if stripped.startswith(k):
                            added_keys.add(k)
                new_lines.append(line)

            if in_section:
                for k, v in overrides.items():
                    if k not in added_keys:
                        new_lines.append(f"{k}={v}")

            with open(reg_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        else:
            with open(reg_path, "a", encoding="utf-8") as f:
                f.write(f"\n{section_header} 1700000000\n#time=1d7a9b0c\n")
                for k, v in overrides.items():
                    f.write(f"{k}={v}\n")

        print(f"[Wine Override] Đã cấu hình DllOverrides vào {reg_path}")
        return True
    except Exception as e:
        print(f"[Wine Override Error] {reg_path}: {e}")
        return False


def find_wuwa_steam_appids() -> list[str]:
    """Tìm tất cả Steam AppID liên quan đến Wuthering Waves."""
    appids = {STEAM_APP_ID, "3513350", "2358720"}
    for p in glob.glob(os.path.expanduser("~/.local/share/Steam/steamapps/appmanifest_*.acf")) + \
             glob.glob(os.path.expanduser("~/.steam/steam/steamapps/appmanifest_*.acf")) + \
             glob.glob(os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/appmanifest_*.acf")):
        try:
            with open(p, "r", errors="ignore") as f:
                txt = f.read()
            if "wuthering" in txt.lower():
                m = re.search(r'\"appid\"\s*\"(\d+)\"', txt)
                if m:
                    appids.add(m.group(1))
        except Exception:
            pass
    return list(appids)


def set_steam_launch_options(launch_opts: str = r'WINEDLLOVERRIDES=\"winhttp=n,b\" %command%') -> int:
    """
    Ghi trực tiếp LaunchOptions vào file localconfig.vdf của Steam cho Wuthering Waves.
    """
    vdf_patterns = [
        "~/.local/share/Steam/userdata/*/config/localconfig.vdf",
        "~/.steam/steam/userdata/*/config/localconfig.vdf",
        "~/.steam/root/userdata/*/config/localconfig.vdf",
        "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/userdata/*/config/localconfig.vdf",
        "~/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/*/config/localconfig.vdf",
    ]

    appids = find_wuwa_steam_appids()
    updated = 0

    found_files = set()
    for pat in vdf_patterns:
        for p in glob.glob(os.path.expanduser(pat)):
            found_files.add(p)

    for path in found_files:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            apps_idx = content.find('"apps"')
            if apps_idx == -1:
                apps_idx = content.lower().find('"apps"')

            if apps_idx != -1:
                head = content[:apps_idx]
                tail = content[apps_idx:]
                file_changed = False

                for app_id in appids:
                    pat = re.compile(r'(\"' + re.escape(app_id) + r'\"\s*\{)([\s\S]*?)(\n\t*\})')
                    m = pat.search(tail)
                    if m:
                        block_hdr, block_body, block_foot = m.group(1), m.group(2), m.group(3)
                        if re.search(r'\"LaunchOptions\"', block_body):
                            new_body = re.sub(
                                r'\"LaunchOptions\"[^\r\n]*',
                                f'"LaunchOptions"\t\t"{launch_opts}"',
                                block_body
                            )
                        else:
                            new_body = f'\n\t\t\t\t\t\t"LaunchOptions"\t\t"{launch_opts}"' + block_body
                        
                        if new_body != block_body:
                            tail = tail[:m.start()] + block_hdr + new_body + block_foot + tail[m.end():]
                            file_changed = True
                    else:
                        apps_hdr_m = re.search(r'(\"apps\"\s*\{)', tail, re.IGNORECASE)
                        if apps_hdr_m:
                            insert_block = f'\n\t\t\t\t\t"{app_id}"\n\t\t\t\t\t{{\n\t\t\t\t\t\t"LaunchOptions"\t\t"{launch_opts}"\n\t\t\t\t\t}}'
                            pos = apps_hdr_m.end()
                            tail = tail[:pos] + insert_block + tail[pos:]
                            file_changed = True

                if file_changed:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(head + tail)
                    print(f"[Steam LaunchOptions] Đã ghi WINEDLLOVERRIDES vào {path}")
                    updated += 1
        except Exception as e:
            print(f"[Steam LaunchOptions Error] {path}: {e}")

    return updated


def install_wine_dll_overrides() -> dict:
    """
    Tự động quét và cài đặt WINEDLLOVERRIDES (winhttp=n,b, dxgi=n,b, d3d11, d3d12, version) vào:
    1. Cấu hình Steam Launch Options: WINEDLLOVERRIDES="winhttp=n,b" %command% (localconfig.vdf)
    2. Tất cả Steam Proton compatdata prefix (user.reg)
    3. Tất cả Heroic / Lutris / Bottles / Wine prefix (user.reg)
    4. Cấu hình Heroic Games Launcher (GamesConfig/*.json)
    """
    applied_count = 0
    search_patterns = [
        "~/.local/share/Steam/steamapps/compatdata/*/pfx/user.reg",
        "~/.steam/steam/steamapps/compatdata/*/pfx/user.reg",
        "~/.steam/root/steamapps/compatdata/*/pfx/user.reg",
        "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/*/pfx/user.reg",
        "~/.var/app/com.valvesoftware.Steam/.steam/steam/steamapps/compatdata/*/pfx/user.reg",
        "~/.var/app/com.heroicgameslauncher.hgl/data/prefixes/*/pfx/user.reg",
        "~/.var/app/com.heroicgameslauncher.hgl/data/prefixes/*/user.reg",
        "~/Games/*/pfx/user.reg",
        "~/Games/*/user.reg",
        "~/.wine/user.reg",
    ]

    game_path = detect_game_path()
    if game_path:
        cur = game_path
        for _ in range(5):
            pfx_reg = os.path.join(cur, "pfx", "user.reg")
            user_reg = os.path.join(cur, "user.reg")
            if os.path.isfile(pfx_reg):
                search_patterns.append(pfx_reg)
            if os.path.isfile(user_reg):
                search_patterns.append(user_reg)
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    found_regs = set()
    for pat in search_patterns:
        for p in glob.glob(os.path.expanduser(pat)):
            found_regs.add(p)

    for reg_file in found_regs:
        if _inject_dll_overrides_into_reg(reg_file):
            applied_count += 1

    # Steam Launch Options & fix
    try:
        steam_vdfs = set_steam_launch_options()
        applied_count += steam_vdfs
    except Exception as e:
        print(f"[Steam LaunchOptions Fix Error] {e}")

    try:
        fix_steam_launch_options()
    except Exception as e:
        print(f"[Steam Config Fix Error] {e}")

    # Heroic configs
    try:
        optimize_heroic_config()
        applied_count += 1
    except Exception as e:
        print(f"[Heroic Config Fix Error] {e}")

    return {
        "ok": True,
        "count": applied_count,
        "message": f"Đã tự động cài WINEDLLOVERRIDES=\"winhttp=n,b\" %command% vào Steam Launch Options & {applied_count} prefix Wine/Proton!",
    }


def fix_heroic_launch_options():
    """Alias cho optimize_heroic_config."""
    optimize_heroic_config()


def launch_game() -> bool:
    """
    Khởi chạy Wuthering Waves qua launcher được cấu hình (Steam hoặc Heroic Launcher).
    """
    info = get_launcher_info()
    current_launcher = info.get("current", "steam")

    exe = get_game_exe()
    if not exe:
        raise FileNotFoundError("Không tìm thấy game executable. Hãy chọn thư mục game.")

    if not exe.endswith(".exe"):
        # Native Linux binary, chạy thẳng
        subprocess.Popen([exe], cwd=os.path.dirname(exe))
        return True

    # ── Chạy qua Heroic Launcher (chế độ ẩn GUI / headless) ────────────────────
    if current_launcher == "heroic":
        optimize_heroic_config()
        heroic_game = detect_heroic_game()
        if heroic_game:
            runner = heroic_game.get("runner", "sideload")
            app_name = heroic_game.get("app_name")
            heroic_url = f"heroic://launch/{runner}/{app_name}"
            print(f"[Launch] Chạy qua Heroic Games Launcher: {heroic_url}")

            # 1. Thử qua xdg-open (chuẩn URL protocol của Heroic trên Linux)
            try:
                subprocess.Popen(["xdg-open", heroic_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass

            # 2. Thử qua lệnh heroic trực tiếp
            try:
                subprocess.Popen(["heroic", heroic_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass

            # 3. Thử qua flatpak
            try:
                subprocess.Popen(["flatpak", "run", "com.heroicgameslauncher.hgl", heroic_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass

        # Nếu chưa tìm thấy game map trong config, mở Heroic
        print("[Launch] Mở Heroic Launcher...")
        try:
            subprocess.Popen(["xdg-open", "heroic://"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            try:
                subprocess.Popen(["heroic"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
        raise RuntimeError("Không thể mở Heroic Games Launcher. Hãy kiểm tra cài đặt Heroic.")

    # ── Chạy qua Steam (headless runtime) ─────────────────────────────────────
    fix_steam_launch_options()
    steam_cmd = ["steam", "-silent", "-applaunch", STEAM_APP_ID]
    if get_dx11_mode():
        steam_cmd.append("-dx11")
    if get_csharp_env_mode():
        steam_cmd.append("-ForceEnableCSharpEnvironment")

    print(f"[Launch] {' '.join(steam_cmd)}")
    try:
        subprocess.Popen(
            steam_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        pass

    # ── Fallback: steam:// URL ────────────────────────────────────────────────
    print("[Launch] steam không tìm thấy, thử steam:// URL...")
    try:
        subprocess.Popen(
            ["xdg-open", f"steam://rungameid/{STEAM_APP_ID}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        pass

    raise RuntimeError(
        "Không tìm thấy Steam. Hãy cài Steam hoặc đổi sang Heroic Launcher để chạy Wuthering Waves trên Linux."
    )



def force_kill_game():
    """Force kill all active Wuthering Waves processes and hanging runners."""
    killed = 0
    if HAS_PSUTIL:
        for p in psutil.process_iter(["name", "cmdline", "pid", "status"]):
            try:
                pname = (p.info.get("name") or "").lower()
                cmdline = " ".join(p.info.get("cmdline") or []).lower()
                
                # Bỏ qua launcher chính
                if "launcher.py" in cmdline or "dangdevvh" in cmdline:
                    continue
                    
                if any(k in pname or k in cmdline for k in ["client-win64-shipping", "client-win64-sh", "wutheringwaves"]):
                    try:
                        p.kill()
                        killed += 1
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception:
                pass
                
    subprocess.run(["pkill", "-9", "-f", "Client-Win64-Shipping"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "WutheringWaves"], capture_output=True)

def open_game_folder():
    """Open the game folder in file manager."""
    game = detect_game_path()
    if not game:
        raise FileNotFoundError("Không tìm thấy thư mục game")
    subprocess.Popen(["xdg-open", game])

def install_paks(pak_source_dir: str = None) -> list[str]:
    """Copy downloaded files to the correct game directories.
    
    Skips font PAK files — fonts are installed separately via the
    font management feature so users can choose custom fonts.
    Returns list of installed files.
    """
    if not pak_source_dir:
        pak_source_dir = get_paks_dir()

    game_dir = detect_game_path()
    if not game_dir:
        return []
        
    pak_dir = os.path.join(game_dir, PAK_SUBPATH)
    bin_dir = os.path.join(game_dir, "Client/Binaries/Win64")
    
    os.makedirs(pak_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)
    
    installed = []
    sources = [pak_source_dir]
    bundled = get_bundled_paks_dir()
    if os.path.isdir(bundled) and bundled not in sources:
        sources.append(bundled)

    seen = set()
    for sdir in sources:
        if not os.path.isdir(sdir):
            continue
        for f in os.listdir(sdir):
            if f in seen:
                continue
            src = os.path.join(sdir, f)
            # Skip font PAK files — they are managed separately
            if "font" in f.lower() and f.endswith(".pak"):
                continue
            if f.endswith(".pak"):
                dst = os.path.join(pak_dir, f)
                shutil.copy2(src, dst)
                installed.append(f)
                seen.add(f)
            elif f == "winhttp.dll":
                dst = os.path.join(bin_dir, f)
                shutil.copy2(src, dst)
                installed.append(f)
                seen.add(f)
    return installed

def get_vh_version() -> str | None:
    cfg = load_config()
    return cfg.get("vh_version")

def set_vh_version(version: str):
    cfg = load_config()
    cfg["vh_version"] = version
    save_config(cfg)

def uninstall_paks() -> list[str]:
    """Remove VH pak files and winhttp.dll from game directory. Returns list of removed files."""
    game_dir = detect_game_path()
    if not game_dir:
        return []
        
    pak_dir = os.path.join(game_dir, PAK_SUBPATH)
    bin_dir = os.path.join(game_dir, "Client/Binaries/Win64")
    
    removed = []
    if os.path.isdir(pak_dir):
        for f in os.listdir(pak_dir):
            if "_99_P.pak" in f or "_99_P.utoc" in f or "_99_P.ucas" in f:
                try:
                    os.remove(os.path.join(pak_dir, f))
                    removed.append(f)
                except Exception:
                    pass
                    
    dll_path = os.path.join(bin_dir, "winhttp.dll")
    if os.path.exists(dll_path):
        try:
            os.remove(dll_path)
            removed.append("winhttp.dll")
        except Exception:
            pass
            
    set_vh_version("")
    return removed

def get_theme() -> str:
    """Return the saved theme ID, defaults to 'modern'."""
    cfg = load_config()
    return cfg.get("theme", "modern")


def set_theme(theme_id: str) -> dict:
    """Save the selected theme ID to config."""
    cfg = load_config()
    cfg["theme"] = theme_id
    save_config(cfg)
    return {"theme": theme_id}


def get_dx11_mode() -> bool:
    """Return whether DirectX 11 mode is enabled (defaults to True on Linux for anti-crash stability)."""
    cfg = load_config()
    return cfg.get("use_dx11", True)


def set_dx11_mode(enabled: bool) -> dict:
    """Set DirectX 11 mode in config and sync to Heroic config."""
    cfg = load_config()
    cfg["use_dx11"] = bool(enabled)
    save_config(cfg)
    optimize_heroic_config()
    return {"use_dx11": cfg["use_dx11"]}


def get_csharp_env_mode() -> bool:
    """Return whether ForceEnableCSharpEnvironment mode is enabled."""
    cfg = load_config()
    return cfg.get("use_csharp_env", True)


def set_csharp_env_mode(enabled: bool) -> dict:
    """Set ForceEnableCSharpEnvironment mode in config and sync to Heroic config."""
    cfg = load_config()
    cfg["use_csharp_env"] = bool(enabled)
    save_config(cfg)
    optimize_heroic_config()
    return {"use_csharp_env": cfg["use_csharp_env"]}


def get_status() -> dict:
    """Return current status as dict for frontend."""
    game_path = detect_game_path()
    pak_dir   = get_pak_dir()
    running   = is_game_running()

    installed_paks = []
    if pak_dir and os.path.isdir(pak_dir):
        installed_paks = [f for f in os.listdir(pak_dir) if "_99_P" in f]

    return {
        "game_path":      game_path,
        "pak_dir":        pak_dir,
        "game_running":   running,
        "installed_paks":  installed_paks,
        "installed_vh":   len(installed_paks) > 0 or bool(get_vh_version()),
        "has_game":       game_path is not None,
        "vh_version":     get_vh_version(),
        "font_status":    get_font_status(),
        "launcher_info":  get_launcher_info(),
        "theme":          get_theme(),
        "use_dx11":       get_dx11_mode(),
        "use_csharp_env": get_csharp_env_mode(),
    }


# ── Font Management ──────────────────────────────────────────────────────────

CUSTOM_FONT_PAK_NAME = "zzz_CustomFont_99_P.pak"
DEFAULT_FONT_PAK_NAME = "zzz_Default_font_99_P.pak"
LEGACY_CUSTOM_FONT_PAK = "CustomFont_99_P.pak"
LEGACY_DEFAULT_FONT_PAK = "Default_font_99_P.pak"


def get_font_status() -> dict:
    """Return the current font installation status."""
    pak_dir = get_pak_dir()
    cfg = load_config()

    status = {
        "active_font": "none",       # "default" | "custom" | "none"
        "custom_font_name": None,    # Original font file name
        "default_available": True,   # Can always install/download on-demand
    }

    if not pak_dir or not os.path.isdir(pak_dir):
        return status

    has_custom = (
        os.path.isfile(os.path.join(pak_dir, CUSTOM_FONT_PAK_NAME)) or
        os.path.isfile(os.path.join(pak_dir, LEGACY_CUSTOM_FONT_PAK))
    )
    has_default = (
        os.path.isfile(os.path.join(pak_dir, DEFAULT_FONT_PAK_NAME)) or
        os.path.isfile(os.path.join(pak_dir, LEGACY_DEFAULT_FONT_PAK))
    )
    has_default_disabled = (
        os.path.isfile(os.path.join(pak_dir, DEFAULT_FONT_PAK_NAME + ".disabled")) or
        os.path.isfile(os.path.join(pak_dir, LEGACY_DEFAULT_FONT_PAK + ".disabled"))
    )

    if has_custom:
        status["active_font"] = "custom"
        status["custom_font_name"] = cfg.get("custom_font_name", "Custom Font")
    elif has_default:
        status["active_font"] = "default"
    elif has_default_disabled:
        status["active_font"] = "none"

    return status


def install_font_from_pak(pak_file_path: str) -> dict:
    """
    Install a custom font directly from an existing PAK file.
    Renames the file to zzz_CustomFont_99_P.pak and copies to wuwaVietHoa.
    """
    if not pak_file_path or not os.path.isfile(pak_file_path):
        raise FileNotFoundError("Không tìm thấy file font PAK đã chọn.")

    game_dir = detect_game_path()
    if not game_dir:
        raise FileNotFoundError("Không tìm thấy thư mục game. Hãy chọn thư mục game trước.")

    pak_dir = os.path.join(game_dir, PAK_SUBPATH)
    os.makedirs(pak_dir, exist_ok=True)

    # Clean any legacy font files in ~mods if any exist to prevent UE4 crash
    _clean_mods_dir_fonts(game_dir)

    # Disable existing font files in game pak dir
    _disable_all_fonts(pak_dir)

    # Copy and rename PAK to wuwaVietHoa (mounted by winhttp.dll)
    dst = os.path.join(pak_dir, CUSTOM_FONT_PAK_NAME)
    shutil.copy2(pak_file_path, dst)

    # Save font name in config (use filename without extension)
    base_name = os.path.basename(pak_file_path)
    font_name = os.path.splitext(base_name)[0]
    for prefix in ("zzz_", "CustomFont_", "Default_font_"):
        if font_name.startswith(prefix):
            font_name = font_name[len(prefix):]

    cfg = load_config()
    cfg["custom_font_name"] = font_name
    cfg["custom_font_source"] = base_name
    save_config(cfg)

    return {
        "ok": True,
        "font_name": font_name,
        "pak_file": CUSTOM_FONT_PAK_NAME,
    }


def install_custom_font(font_file_path: str) -> dict:
    """
    Install a custom TTF/OTF or PAK font into the game.
    If .pak is provided, directly installs via install_font_from_pak.
    Otherwise converts TTF/OTF → PAK using font_packer.
    """
    if not font_file_path or not os.path.isfile(font_file_path):
        raise FileNotFoundError("Không tìm thấy file font đã chọn.")

    if font_file_path.lower().endswith(".pak"):
        return install_font_from_pak(font_file_path)

    from backend import font_packer

    game_dir = detect_game_path()
    if not game_dir:
        raise FileNotFoundError("Không tìm thấy thư mục game. Hãy chọn thư mục game trước.")

    pak_dir = os.path.join(game_dir, PAK_SUBPATH)
    os.makedirs(pak_dir, exist_ok=True)

    # Clean any legacy font files in ~mods if any exist to prevent UE4 crash
    _clean_mods_dir_fonts(game_dir)

    # Build PAK from font file
    base_pak_dir = get_paks_dir()
    output_pak = os.path.join(base_pak_dir, CUSTOM_FONT_PAK_NAME)
    font_packer.build_font_pak(font_file_path, output_pak)

    # Disable existing font files in game pak dir
    _disable_all_fonts(pak_dir)

    # Copy new font PAK to wuwaVietHoa (mounted by winhttp.dll)
    dst = os.path.join(pak_dir, CUSTOM_FONT_PAK_NAME)
    shutil.copy2(output_pak, dst)

    # Save font name in config
    font_name = font_packer.get_font_name(font_file_path)
    cfg = load_config()
    cfg["custom_font_name"] = font_name
    cfg["custom_font_source"] = os.path.basename(font_file_path)
    save_config(cfg)

    return {
        "ok": True,
        "font_name": font_name,
        "pak_file": CUSTOM_FONT_PAK_NAME,
    }


def install_default_font() -> dict:
    """
    Install the default Vietnamese font into the game.
    Downloads Default_font_99_P.pak on-demand if not already cached.
    """
    from backend import downloader

    game_dir = detect_game_path()
    if not game_dir:
        raise FileNotFoundError("Không tìm thấy thư mục game.")

    pak_dir = os.path.join(game_dir, PAK_SUBPATH)
    os.makedirs(pak_dir, exist_ok=True)

    # Clean any legacy font files in ~mods if any exist to prevent UE4 crash
    _clean_mods_dir_fonts(game_dir)

    base_pak_dir = get_paks_dir()
    os.makedirs(base_pak_dir, exist_ok=True)
    src = os.path.join(base_pak_dir, "Default_font_99_P.pak")

    # If missing in writable paks, check bundled paks
    bundled_src = os.path.join(get_bundled_paks_dir(), "Default_font_99_P.pak")
    if (not os.path.isfile(src) or os.path.getsize(src) == 0) and os.path.isfile(bundled_src) and os.path.getsize(bundled_src) > 0:
        shutil.copy2(bundled_src, src)

    # Download default font on-demand if missing
    if not os.path.isfile(src) or os.path.getsize(src) == 0:
        try:
            ver_info = downloader.get_version_info()
            version = ver_info.get("version")
            href = downloader.mint_href("font", version)
            downloader.download_file(href, src)
        except Exception as e:
            raise RuntimeError(f"Không thể tải font mặc định từ máy chủ: {e}")

    # Remove all custom/other font PAKs
    _disable_all_fonts(pak_dir)

    # Copy default font into wuwaVietHoa
    dst = os.path.join(pak_dir, DEFAULT_FONT_PAK_NAME)
    shutil.copy2(src, dst)

    # Clear custom font config
    cfg = load_config()
    cfg.pop("custom_font_name", None)
    cfg.pop("custom_font_source", None)
    save_config(cfg)

    return {"ok": True, "font_name": "LaguSans Bold (Mặc định)"}


def _clean_mods_dir_fonts(game_dir: str):
    """Clean up any font PAK files mistakenly placed in Client/Content/Paks/~mods."""
    mods_dir = os.path.join(game_dir, "Client", "Content", "Paks", "~mods")
    if os.path.isdir(mods_dir):
        _disable_all_fonts(mods_dir)


def _disable_all_fonts(pak_dir: str):
    """Remove/disable all font-related PAK files from the given directory."""
    if not os.path.exists(pak_dir):
        return
    font_paks = [
        CUSTOM_FONT_PAK_NAME,
        DEFAULT_FONT_PAK_NAME,
        DEFAULT_FONT_PAK_NAME + ".disabled",
        LEGACY_CUSTOM_FONT_PAK,
        LEGACY_DEFAULT_FONT_PAK,
        LEGACY_DEFAULT_FONT_PAK + ".disabled",
    ]
    for f in font_paks:
        path = os.path.join(pak_dir, f)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

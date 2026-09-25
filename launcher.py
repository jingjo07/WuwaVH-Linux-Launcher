#!/usr/bin/env python3
"""
WuWaVH Linux Launcher — Entry Point
GTK3 + WebKit2GTK 4.1 window embedding the web frontend.
"""

import gi
gi.require_version("Gtk",       "3.0")
gi.require_version("WebKit2",   "4.1")
gi.require_version("Gdk",       "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, WebKit2, GLib, Gdk, GdkPixbuf

GLib.set_prgname("wuwavh-launcher")
GLib.set_application_name("WuWaVH Launcher")

import sys, os, json, threading, time

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR       = os.path.join(BASE_DIR, "frontend")
BUNDLED_ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")
USER_ASSETS_DIR    = os.path.expanduser("~/.config/wuwavh/assets")

sys.path.insert(0, BASE_DIR)
from backend import downloader, game, performance, version

PAK_DIR = game.get_paks_dir()

def get_effective_assets_dir() -> str:
    """Get assets dir for WebKit media. Prioritizes user updated media if present, else bundled."""
    if os.path.isfile(os.path.join(USER_ASSETS_DIR, "bg-video-720p.mp4")) and os.path.getsize(os.path.join(USER_ASSETS_DIR, "bg-video-720p.mp4")) > 0:
        return USER_ASSETS_DIR
    return BUNDLED_ASSETS_DIR

def get_writable_assets_dir() -> str:
    """Get writable directory to download new/updated media assets."""
    if os.environ.get("APPDIR") or os.environ.get("APPIMAGE") or not os.access(BUNDLED_ASSETS_DIR, os.W_OK):
        os.makedirs(USER_ASSETS_DIR, exist_ok=True)
        return USER_ASSETS_DIR
    return BUNDLED_ASSETS_DIR

ASSETS_DIR = get_effective_assets_dir()

# ── IPC Handler ──────────────────────────────────────────────────────────────

class IPC:
    """Handles JS <-> Python communication."""

    def __init__(self, window: "LauncherWindow"):
        self.win = window

    def dispatch(self, msg: dict):
        action = msg.get("action", "")
        req_id = msg.get("id")
        data   = msg.get("data", {})

        # Non-blocking: run in thread
        threading.Thread(
            target=self._handle,
            args=(action, req_id, data),
            daemon=True
        ).start()

    def _handle(self, action: str, req_id, data: dict):
        try:
            result = self._dispatch_action(action, data)
            self._reply(req_id, result)
        except Exception as e:
            self._reply(req_id, {"error": str(e)})

    def _dispatch_action(self, action: str, data: dict) -> dict:
        match action:
            case "window_minimize":
                GLib.idle_add(self.win.iconify)
                return {}
            case "window_close":
                GLib.idle_add(Gtk.main_quit)
                return {}
            case "window_drag_start":
                GLib.idle_add(self.win.start_drag,
                              data.get("x", 0), data.get("y", 0))
                return {}

            case "get_version":
                return downloader.get_version_info()

            case "get_status":
                return game.get_status()

            case "open_game_folder":
                game.open_game_folder()
                return {"ok": True}

            case "open_url":
                url = data.get("url", "")
                if url.startswith(("http://", "https://", "discord://")):
                    import subprocess
                    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"ok": True}
                raise ValueError("URL không hợp lệ")

            case "set_game_path":
                path = data.get("path", "")
                if os.path.isdir(path):
                    game.set_game_path(path)
                    return {"ok": True}
                raise ValueError("Thư mục không hợp lệ")

            case "launch_game":
                ok = game.launch_game()
                return {"ok": ok}

            case "force_kill" | "kill_game":
                game.force_kill_game()
                return {"ok": True, "killed": True}

            case "update_vh" | "update_mod":
                # Run in separate thread so _dispatch_action returns immediately
                threading.Thread(target=self._do_update_vh, daemon=True).start()
                return {"status": "started"}

            case "update_launcher_assets" | "update_assets":
                threading.Thread(target=self._do_update_assets, daemon=True).start()
                return {"status": "started"}

            case "set_vh_version":
                game.set_vh_version(data.get("version", ""))
                return {"ok": True}

            case "install_paks" | "install_mod":
                installed = game.install_paks(PAK_DIR)
                return {"installed": installed}

            case "uninstall_vh" | "uninstall_mod":
                removed = game.uninstall_paks()
                return {"removed": removed}

            # ── Font Management ──────────────────────────────────
            case "pick_font_file":
                path = self._pick_font_file()
                return {"path": path}

            case "pick_font_pak":
                path = self._pick_pak_file()
                return {"path": path}

            case "install_font":
                font_path = data.get("path", "")
                if not font_path or not os.path.isfile(font_path):
                    raise ValueError("File font không hợp lệ")
                result = game.install_custom_font(font_path)
                return result

            case "install_font_from_pak":
                pak_path = data.get("path", "")
                if not pak_path or not os.path.isfile(pak_path):
                    raise ValueError("File PAK không hợp lệ")
                result = game.install_font_from_pak(pak_path)
                return result

            case "install_default_font":
                result = game.install_default_font()
                return result

            case "get_font_status":
                return game.get_font_status()

            # ── Launcher Selection (Steam / Heroic) ───────────────
            case "get_launcher_info":
                return game.get_launcher_info()

            case "set_launcher":
                launcher_type = data.get("launcher", "steam")
                return game.set_preferred_launcher(launcher_type)

            # ── Theme Management ──────────────────────────────────
            case "get_theme":
                return {"theme": game.get_theme()}

            case "set_theme":
                theme_id = data.get("theme", "modern")
                return game.set_theme(theme_id)

            # ── DirectX 11 Mode ───────────────────────────────────
            case "get_dx11_mode":
                return {"use_dx11": game.get_dx11_mode()}

            case "set_dx11_mode":
                enabled = data.get("enabled", True)
                return game.set_dx11_mode(enabled)

            # ── CSharp Environment Mode ───────────────────────────
            case "get_csharp_env_mode":
                return {"use_csharp_env": game.get_csharp_env_mode()}

            case "set_csharp_env_mode":
                enabled = data.get("enabled", True)
                return game.set_csharp_env_mode(enabled)

            # ── Wine DLL Overrides (WINEOVERDRIVE) ────────────────
            case "install_wine_overrides" | "install_wine_overdrive":
                return game.install_wine_dll_overrides()

            # ── High Performance Mode ─────────────────────────────
            case "get_perf_settings":
                return performance.get_perf_settings()

            case "save_perf_settings":
                new_settings = data.get("settings", {})
                return performance.save_and_apply_perf_settings(new_settings)

            case "restore_perf_settings":
                return performance.restore_default_ini()

            case "apply_perf_preset":
                preset_name = data.get("preset", "default")
                return performance.apply_perf_preset(preset_name)

            case "get_engine_ini_text" | "get_engine_ini":
                return {"text": performance.get_current_engine_ini_text()}

            case "ping":
                return {"pong": True}

            case _:
                raise ValueError(f"Unknown action: {action}")

    def _pick_font_file(self) -> str | None:
        """Open a GTK file chooser dialog for TTF/OTF/PAK files. Must run on main thread."""
        result = [None]
        event = threading.Event()

        def _show_dialog():
            dialog = Gtk.FileChooserDialog(
                title="Chọn file font (TTF / OTF / PAK)",
                parent=self.win,
                action=Gtk.FileChooserAction.OPEN,
            )
            dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
            )

            # Filter for font & pak files
            ff = Gtk.FileFilter()
            ff.set_name("Font files (*.ttf, *.otf, *.pak)")
            ff.add_pattern("*.ttf")
            ff.add_pattern("*.TTF")
            ff.add_pattern("*.otf")
            ff.add_pattern("*.OTF")
            ff.add_pattern("*.pak")
            ff.add_pattern("*.PAK")
            dialog.add_filter(ff)

            # All files filter
            af = Gtk.FileFilter()
            af.set_name("Tất cả file")
            af.add_pattern("*")
            dialog.add_filter(af)

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                result[0] = dialog.get_filename()
            dialog.destroy()
            event.set()

        GLib.idle_add(_show_dialog)
        event.wait(timeout=120)  # Wait up to 2 min for user to pick
        return result[0]

    def _pick_pak_file(self) -> str | None:
        """Open a GTK file chooser dialog for PAK font files."""
        result = [None]
        event = threading.Event()

        def _show_dialog():
            dialog = Gtk.FileChooserDialog(
                title="Chọn file Font PAK (*.pak)",
                parent=self.win,
                action=Gtk.FileChooserAction.OPEN,
            )
            dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
            )

            # Filter for PAK files
            ff = Gtk.FileFilter()
            ff.set_name("Unreal Engine PAK (*.pak)")
            ff.add_pattern("*.pak")
            ff.add_pattern("*.PAK")
            dialog.add_filter(ff)

            # All files filter
            af = Gtk.FileFilter()
            af.set_name("Tất cả file")
            af.add_pattern("*")
            dialog.add_filter(af)

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                result[0] = dialog.get_filename()
            dialog.destroy()
            event.set()

        GLib.idle_add(_show_dialog)
        event.wait(timeout=120)
        return result[0]

    def _do_update_vh(self):
        """Download paks with progress events (runs in its own thread)."""
        os.makedirs(PAK_DIR, exist_ok=True)
        try:
            ver_info = downloader.get_version_info()
            version  = ver_info.get("version")

            total_providers = len(downloader.PROVIDERS)
            for idx, (provider, filename, label) in enumerate(downloader.PROVIDERS):
                dest = os.path.join(PAK_DIR, filename)

                self.emit("update_progress", {
                    "phase":    "mint",
                    "file":     filename,
                    "label":    label,
                    "step":     idx,
                    "total":    total_providers,
                    "progress": 0,
                })

                if provider == "raw":
                    href = downloader.get_raw_dll_url(filename)
                else:
                    href = downloader.mint_href(provider, version)

                t_last = [time.monotonic()]
                b_last = [0]
                speed_smooth = [0.0]
                speed_cache = [""]

                def _progress(done, total, f=filename, i=idx):
                    now = time.monotonic()
                    dt = now - t_last[0]
                    if dt >= 0.35:
                        instant = (done - b_last[0]) / (1_048_576 * dt)
                        if speed_smooth[0] <= 0.0:
                            speed_smooth[0] = instant
                        else:
                            speed_smooth[0] = 0.70 * speed_smooth[0] + 0.30 * instant
                        s = speed_smooth[0]
                        speed_cache[0] = f"{s:.1f} MB/s" if s >= 0.1 else f"{s*1024:.0f} KB/s"
                        t_last[0] = now
                        b_last[0] = done

                    pct = done / total if total else 0
                    self.emit("update_progress", {
                        "phase":    "download",
                        "file":     f,
                        "step":     i,
                        "total":    total_providers,
                        "progress": pct,
                        "mb_done":  round(done  / 1_048_576, 1),
                        "mb_total": round(total / 1_048_576, 1),
                        "speed":    speed_cache[0],
                    })

                downloader.download_file(href, dest, _progress)
                sha = downloader.sha256_file(dest)
                self.emit("update_progress", {
                    "phase":    "done_file",
                    "file":     filename,
                    "step":     idx + 1,
                    "total":    total_providers,
                    "progress": 1.0,
                    "sha256":   sha[:16],
                })

            # Automatically copy and install downloaded paks & dll into the game directory
            installed = game.install_paks(PAK_DIR)
            if version:
                game.set_vh_version(version)

            self.emit("update_done", {"version": version, "installed": installed})

        except Exception as e:
            self.emit("update_error", {"error": str(e)})

    def _do_update_assets(self):
        """Download official Kuro Games background video and music assets with progress events."""
        writable_assets = get_writable_assets_dir()
        try:
            web_assets = downloader.get_web_assets()
            total_assets = len(web_assets)
            for idx, (filename, url, label) in enumerate(web_assets):
                dest = os.path.join(writable_assets, filename)

                self.emit("update_assets_progress", {
                    "file":     filename,
                    "label":    label,
                    "step":     idx,
                    "total":    total_assets,
                    "progress": 0,
                })

                t_last = [time.monotonic()]
                b_last = [0]
                speed_smooth = [0.0]
                speed_cache = [""]

                def _progress(done, total, f=filename, i=idx):
                    now = time.monotonic()
                    dt = now - t_last[0]
                    if dt >= 0.35:
                        instant = (done - b_last[0]) / (1_048_576 * dt)
                        if speed_smooth[0] <= 0.0:
                            speed_smooth[0] = instant
                        else:
                            speed_smooth[0] = 0.70 * speed_smooth[0] + 0.30 * instant
                        s = speed_smooth[0]
                        speed_cache[0] = f"{s:.1f} MB/s" if s >= 0.1 else f"{s*1024:.0f} KB/s"
                        t_last[0] = now
                        b_last[0] = done

                    pct = done / total if total else 0
                    self.emit("update_assets_progress", {
                        "file":     f,
                        "step":     i,
                        "total":    total_assets,
                        "progress": pct,
                        "mb_done":  round(done  / 1_048_576, 1),
                        "mb_total": round(total / 1_048_576, 1),
                        "speed":    speed_cache[0],
                    })

                downloader.download_file(url, dest, _progress)
                self.emit("update_assets_progress", {
                    "file":     filename,
                    "label":    label,
                    "step":     idx + 1,
                    "total":    total_assets,
                    "progress": 1.0,
                })

            self.emit("update_assets_done", {"status": "ok"})
        except Exception as e:
            self.emit("update_assets_error", {"error": str(e)})


    def emit(self, event: str, data: dict):
        js = f"window.__onEvent({json.dumps(event)}, {json.dumps(data)})"
        GLib.idle_add(self.win.run_js, js)

    def _reply(self, req_id, result):
        if req_id and result is not None:
            js = f"window.__resolve({json.dumps(req_id)}, {json.dumps(result)})"
            GLib.idle_add(self.win.run_js, js)


# ── GTK Window ────────────────────────────────────────────────────────────────

class LauncherWindow(Gtk.Window):
    WIN_W, WIN_H = 1200, 700
    TOPBAR_H     = 60

    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        
        # Force CSD to remove OS title bar on DEs that ignore set_decorated(False)
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(False)
        self.set_titlebar(hb)
        
        self.set_default_size(self.WIN_W, self.WIN_H)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.set_title(f"WuWaVH Launcher v{version.LAUNCHER_VERSION}")

        # Set App Window Icon from frontend/assets/icon.png
        icon_path = os.path.join(ASSETS_DIR, "icon.png")
        if os.path.isfile(icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
                self.set_icon(pixbuf)
                Gtk.Window.set_default_icon(pixbuf)
            except Exception as e:
                print(f"[Icon warning] {e}")

        # Round corners via app-paintable + Cairo
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self._ipc = IPC(self)
        self._drag_start_xy = None

        # ── WebKit2 Context & RAM Optimizations ──
        ctx = WebKit2.WebContext.get_default()
        ctx.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)

        mgr = WebKit2.UserContentManager()
        mgr.register_script_message_handler("backend")
        mgr.connect("script-message-received::backend", self._on_js_message)

        settings = WebKit2.Settings()
        settings.set_enable_javascript(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_media_playback_allows_inline(True)

        # ── RAM & Performance Optimizations ──
        settings.set_enable_media_stream(False)        # No webcam/mic needed
        settings.set_enable_mediasource(False)         # No adaptive streaming (MSE)
        settings.set_enable_developer_extras(False)    # Disable Inspector in production
        settings.set_enable_page_cache(False)          # Single page app, no nav cache
        settings.set_enable_smooth_scrolling(False)    # Fixed-size window, no scroll
        settings.set_enable_webgl(False)               # No 3D WebGL buffer allocation (~50MB RAM saved)
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ON_DEMAND
        )

        # Ensure frontend/version.js is synchronized with version.py
        try:
            v_js_path = os.path.join(FRONTEND_DIR, "version.js")
            with open(v_js_path, "w", encoding="utf-8") as vf:
                vf.write(f'// Auto-generated from backend/version.py\nwindow.LAUNCHER_VERSION = "{version.LAUNCHER_VERSION}";\n')
        except Exception as e:
            print(f"[Version sync warning] {e}")

        # Inject global vars before page load
        inject_script = WebKit2.UserScript(
            f"""
            window.ASSETS_DIR = "file://{ASSETS_DIR}";
            window.PAK_DIR    = "{PAK_DIR}";
            window.LAUNCHER_VERSION = "{version.LAUNCHER_VERSION}";
            """,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            None, None
        )
        mgr.add_script(inject_script)

        # Allow un-muted autoplay in WebKit policies
        policies = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)

        self.webview = WebKit2.WebView(
            user_content_manager=mgr,
            website_policies=policies,
            settings=settings
        )
        self.webview.connect("button-press-event", self._on_button_press)

        index_html = os.path.join(FRONTEND_DIR, "index.html")
        self.webview.load_uri(f"file://{index_html}")

        self.add(self.webview)
        self.show_all()

        self.connect("destroy", Gtk.main_quit)

    # ── JS bridge ────────────────────────────────────────────────────────────

    def _on_js_message(self, mgr, js_result):
        try:
            raw  = js_result.get_js_value().to_json(0)
            msg  = json.loads(raw)
            self._ipc.dispatch(msg)
        except Exception as e:
            print(f"[IPC] parse error: {e}")

    def run_js(self, js: str):
        try:
            self.webview.evaluate_javascript(js, -1, None, None, None, None, None)
        except Exception as e:
            print(f"[JS eval] {e}")

    # ── Window drag ──────────────────────────────────────────────────────────

    def _on_button_press(self, widget, event):
        """Allow dragging only specifically from the left corner logo area (x <= 160, y <= 56)."""
        in_topbar  = event.y <= self.TOPBAR_H
        in_logo_area = event.x <= 160
        if in_topbar and in_logo_area and event.button == 1:
            self.get_window().begin_move_drag(
                event.button,
                int(event.x_root),
                int(event.y_root),
                event.time
            )
            return True
        return False

    def start_drag(self, x, y):
        """Called from JS for dragging."""
        gdk_win = self.get_window()
        if gdk_win:
            gdk_win.begin_move_drag(1, int(x), int(y), Gdk.CURRENT_TIME)


# ── Startup: download media assets if missing ──────────────────────────────

def ensure_assets():
    try:
        writable_assets = get_writable_assets_dir()
        web_assets = downloader.get_web_assets()
        for filename, url, label in web_assets:
            eff_path = os.path.join(get_effective_assets_dir(), filename)
            if os.path.exists(eff_path) and os.path.getsize(eff_path) > 0:
                continue
            dest = os.path.join(writable_assets, filename)
            print(f"[Assets] Downloading {filename} from official Kuro Web...")
            try:
                downloader.download_file(url, dest, lambda d, t: None)
                print(f"[Assets] {filename} OK ({os.path.getsize(dest)//1024} KB)")
            except Exception as e:
                print(f"[Assets] Failed {filename}: {e}")
                if os.path.exists(dest):
                    os.remove(dest)
    except Exception as e:
        print(f"[Assets] ensure_assets error: {e}")


def main():
    os.makedirs(get_writable_assets_dir(), exist_ok=True)
    os.makedirs(PAK_DIR,                  exist_ok=True)

    # Download assets in background (non-blocking)
    threading.Thread(target=ensure_assets, daemon=True).start()

    win = LauncherWindow()
    Gtk.main()


if __name__ == "__main__":
    main()

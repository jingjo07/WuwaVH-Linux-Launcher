#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  ✦ WuWaVH Launcher — AppImage Build Script ✦
#  Đóng gói WuWaVH Launcher thành file thực thi duy nhất (.AppImage)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/build/WuWaVH.AppDir"
OUTPUT_NAME="WuWaVH-Launcher-x86_64.AppImage"

LAUNCHER_VERSION=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from backend.version import LAUNCHER_VERSION; print(LAUNCHER_VERSION)" 2>/dev/null || echo "1.1")

echo "=================================================="
echo "   Đang đóng gói WuWaVH Launcher v${LAUNCHER_VERSION} thành AppImage   "
echo "=================================================="

# 1. Tạo cấu trúc thư mục AppDir
echo "[1/4] Chuẩn bị cấu trúc AppDir..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib"
mkdir -p "$APP_DIR/usr/share/applications"
mkdir -p "$APP_DIR/usr/share/icons/hicolor/256x256/apps"

# 2. Copy source code và tài nguyên
echo "[2/4] Sao chép mã nguồn và tài nguyên..."
cp -r "$SCRIPT_DIR/backend" "$APP_DIR/"
cp -r "$SCRIPT_DIR/frontend" "$APP_DIR/"
cp "$SCRIPT_DIR/launcher.py" "$APP_DIR/"
cp "$SCRIPT_DIR/launcher.sh" "$APP_DIR/"

if [ -d "$SCRIPT_DIR/paks" ]; then
    cp -r "$SCRIPT_DIR/paks" "$APP_DIR/"
fi

# Tích hợp sẵn Aria2c tốc độ cao vào AppImage nếu có trên máy build
if command -v aria2c &>/dev/null; then
    echo "Tích hợp aria2c và libaria2 vào AppDir..."
    cp "$(command -v aria2c)" "$APP_DIR/usr/bin/aria2c"
    if [ -f /usr/lib/libaria2.so.0 ]; then
        cp -d /usr/lib/libaria2.so* "$APP_DIR/usr/lib/" 2>/dev/null || true
    fi
fi

# Icon
if [ -f "$SCRIPT_DIR/wuwavh.png" ]; then
    cp "$SCRIPT_DIR/wuwavh.png" "$APP_DIR/wuwavh.png"
    cp "$SCRIPT_DIR/wuwavh.png" "$APP_DIR/.DirIcon"
    cp "$SCRIPT_DIR/wuwavh.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/wuwavh.png"
elif [ -f "$SCRIPT_DIR/frontend/assets/icon.png" ]; then
    cp "$SCRIPT_DIR/frontend/assets/icon.png" "$APP_DIR/wuwavh.png"
    cp "$SCRIPT_DIR/frontend/assets/icon.png" "$APP_DIR/.DirIcon"
    cp "$SCRIPT_DIR/frontend/assets/icon.png" "$APP_DIR/usr/share/icons/hicolor/256x256/apps/wuwavh.png"
fi

# Desktop Entry
cat << 'EOF' > "$APP_DIR/wuwavh.desktop"
[Desktop Entry]
Name=WuWaVH Launcher
Comment=Wuthering Waves Vietnamese Mod Launcher
Exec=AppRun %U
Icon=wuwavh
Terminal=false
Type=Application
Categories=Game;Utility;
StartupWMClass=wuwavh
EOF
cp "$APP_DIR/wuwavh.desktop" "$APP_DIR/usr/share/applications/"

# AppRun Script
cat << 'EOF' > "$APP_DIR/AppRun"
#!/usr/bin/env bash
set -e

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export APPDIR
export PATH="$APPDIR/usr/bin:$PATH"
export LD_LIBRARY_PATH="$APPDIR/usr/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$APPDIR:$PYTHONPATH"
export XDG_DATA_DIRS="$APPDIR/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# Kiểm tra WebKitGTK trên hệ thống
if command -v python3 &>/dev/null; then
    if python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1'); from gi.repository import Gtk, WebKit2" 2>/dev/null || \
       python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.0'); from gi.repository import Gtk, WebKit2" 2>/dev/null; then
        exec python3 "$APPDIR/launcher.py" "$@"
    fi
fi

# Nếu thiếu WebKitGTK, chuyển sang launcher.sh (YAD/Zenity GUI hoặc CLI fallback)
echo "[WuWaVH] WebKitGTK không khả dụng, đang khởi động chế độ dự phòng YAD/Zenity..."
exec bash "$APPDIR/launcher.sh" "$@"
EOF
chmod +x "$APP_DIR/AppRun"

# 3. Tải appimagetool nếu chưa có
echo "[3/4] Chuẩn bị appimagetool..."
TOOL_PATH="$SCRIPT_DIR/build/appimagetool-x86_64.AppImage"
if [ ! -f "$TOOL_PATH" ]; then
    mkdir -p "$SCRIPT_DIR/build"
    echo "Đang tải appimagetool từ GitHub..."
    curl -L -o "$TOOL_PATH" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" || true
    if [ -f "$TOOL_PATH" ]; then
        chmod +x "$TOOL_PATH"
    fi
fi

# 4. Đóng gói AppImage
echo "[4/4] Đang đóng gói thành $OUTPUT_NAME..."
rm -f "$SCRIPT_DIR/$OUTPUT_NAME"
if [ -f "$TOOL_PATH" ]; then
    ARCH=x86_64 "$TOOL_PATH" "$APP_DIR" "$SCRIPT_DIR/$OUTPUT_NAME" || {
        echo "Thử lại với --appimage-extract-and-run..."
        ARCH=x86_64 "$TOOL_PATH" --appimage-extract-and-run "$APP_DIR" "$SCRIPT_DIR/$OUTPUT_NAME"
    }
    echo "=================================================="
    echo "   THÀNH CÔNG: $SCRIPT_DIR/$OUTPUT_NAME   "
    echo "=================================================="
else
    echo "[!] Không thể tải appimagetool tự động. Thư mục $APP_DIR đã được chuẩn bị sẵn sàng."
    echo "    Bạn có thể dùng lệnh: appimagetool $APP_DIR $OUTPUT_NAME"
fi

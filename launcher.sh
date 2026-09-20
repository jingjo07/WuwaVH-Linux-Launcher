#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  ✦ WuWaVH Launcher — Modern Shell Script with YAD / Zenity GUI ✦
#  Premium Wuthering Waves Vietnamese Mod Launcher for Linux
#
#  Dependencies: yad (or zenity), curl, jq, openssl
#  Usage:        bash launcher.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -uo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAK_DIR="$SCRIPT_DIR/paks"
CONFIG_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/wuwavh/config.json"

# Auto-detect icon
if [ -f "$SCRIPT_DIR/wuwavh.png" ]; then
    ICON_PATH="$SCRIPT_DIR/wuwavh.png"
elif [ -f "$SCRIPT_DIR/frontend/assets/icon.png" ]; then
    ICON_PATH="$SCRIPT_DIR/frontend/assets/icon.png"
elif [ -f "$SCRIPT_DIR/icon.png" ]; then
    ICON_PATH="$SCRIPT_DIR/icon.png"
else
    ICON_PATH=""
fi

# ── Launch Modern WebKit2GTK GUI if available ────────────────────────────────
if [[ "${1:-}" != "--cli" && "${1:-}" != "--yad" && "${1:-}" != "--zenity" ]]; then
    if command -v python3 &>/dev/null && [ -f "$SCRIPT_DIR/launcher.py" ]; then
        if python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1'); from gi.repository import Gtk, WebKit2" 2>/dev/null; then
            exec python3 "$SCRIPT_DIR/launcher.py" "$@"
        fi
    fi
fi

# ── URLs & Constants ──────────────────────────────────────────────────────────
VERSION_URL="https://huggingface.co/datasets/BachMacThanh/DangDevVH/raw/main/Wuwa/version.json"
MINT_URL="https://dl.dangdev.io.vn/o"
PROXY_BOX="WuwaVH"
STEAM_APP_ID="3513350"
GAME_EXE_NAME="Client-Win64-Shipping.exe"
PAK_SUBPATH="Client/Binaries/Win64/wuwaVietHoa"
LAUNCHER_VERSION="2.0"

# ── HMAC Key bytes (XOR of DATA ⊕ MASK, identical to Python) ──────────────────
MASK_BYTES=(58 31 171 83 16 88 50 84 75 123 181 53 137 203 233 194 199 235 87 167 183 153 83 52 249 235 113 178 112 23 153 201)
DATA_BYTES=(109 35 133 66 56 74 42 20 233 192 200 230 94 205 188 185 241 38 182 187 177 46 246 219 72 48 47 126 96 13 119 104)

# ── Providers (format: provider|filename|label) ──────────────────────────────
PROVIDERS=(
    "mod|WuWaVH_99_P.pak|Bản dịch chính (Mod Pak)"
    "font|Default_font_99_P.pak|Font chữ tiếng Việt"
    "raw|winhttp.dll|Proxy DLL (winhttp)"
)

# ── Default game search paths ─────────────────────────────────────────────────
DEFAULT_SEARCH_PATHS=(
    "$HOME/.steam/steam/steamapps/common/Wuthering Waves"
    "$HOME/.local/share/Steam/steamapps/common/Wuthering Waves"
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Wuthering Waves"
    "$HOME/.var/app/com.valvesoftware.Steam/.steam/steam/steamapps/common/Wuthering Waves"
    "$HOME/Games/Wuthering Waves"
    "$HOME/Games/Heroic/Wuthering Waves"
    "$HOME/.var/app/com.heroicgameslauncher.hgl/Games/Wuthering Waves"
    "/opt/wuthering-waves"
)

# ── Terminal colours & Logging ────────────────────────────────────────────────
_C='\033[0;36m'; _G='\033[0;32m'; _Y='\033[1;33m'; _R='\033[0;31m'; _M='\033[0;35m'; _N='\033[0m'
_BOLD='\033[1m'

log()  { echo -e "${_C}✦ [WuWaVH]${_N} $*" >&2; }
ok()   { echo -e "${_G}✔ [WuWaVH]${_N} $*" >&2; }
warn() { echo -e "${_Y}⚠ [WuWaVH]${_N} $*" >&2; }
err()  { echo -e "${_R}✗ [WuWaVH]${_N} $*" >&2; }
info() { echo -e "${_M}ℹ [WuWaVH]${_N} $*" >&2; }

# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY CHECK
# ══════════════════════════════════════════════════════════════════════════════

HAS_YAD=false
HAS_ZENITY=false
USE_CUSTOM_CSS=false
CSS_FILE=""
HMAC_KEY_HEX=""

check_deps() {
    local missing=()

    command -v curl    &>/dev/null || missing+=("curl")
    command -v jq      &>/dev/null || missing+=("jq")
    command -v openssl &>/dev/null || missing+=("openssl")

    if command -v yad &>/dev/null; then
        HAS_YAD=true
    elif command -v zenity &>/dev/null; then
        HAS_ZENITY=true
    else
        missing+=("yad (hoặc zenity)")
    fi

    if (( ${#missing[@]} )); then
        echo -e "${_R}═════════════════════════════════════════════════════════════════════${_N}"
        echo -e "${_BOLD}${_Y}  ✦ WuWaVH Launcher — Thiếu Dependencies Cần Thiết${_N}"
        echo -e "${_R}═════════════════════════════════════════════════════════════════════${_N}"
        echo ""
        echo -e "  Cần cài thêm gói: ${_BOLD}${missing[*]}${_N}"
        echo ""
        echo -e "  ${_C}• Arch Linux  :${_N}  sudo pacman -S yad curl jq openssl"
        echo -e "  ${_C}• Ubuntu/Deb  :${_N}  sudo apt install yad curl jq openssl"
        echo -e "  ${_C}• Fedora      :${_N}  sudo dnf install yad curl jq openssl"
        echo -e "  ${_C}• openSUSE    :${_N}  sudo zypper install yad curl jq openssl"
        echo ""
        exit 1
    fi

    log "Engine giao diện: $($HAS_YAD && echo -e "${_G}YAD (GTK3)${_N}" || echo -e "${_Y}Zenity${_N}")"
}

# ══════════════════════════════════════════════════════════════════════════════
#  GTK3 CSS THEME (Wuthering Waves Celestial Obsidian & Gold)
# ══════════════════════════════════════════════════════════════════════════════

setup_theme() {
    export GTK_THEME="${GTK_THEME:-Adwaita}:dark"
    $HAS_YAD || return 0

    CSS_FILE=$(mktemp /tmp/wuwavh-theme-XXXXXX.css)
    cat > "$CSS_FILE" <<'CSSEOF'
/* ══════════════════════════════════════════════════════════════════════════════
   WuWaVH Launcher — Celestial Obsidian & Royal Gold GTK3 Theme
   ══════════════════════════════════════════════════════════════════════════════ */

/* ── Base Window & Containers ── */
window, dialog, .dialog-vbox, #yad-dialog-window {
    background-color: #0b111e;
    background-image: linear-gradient(165deg, #090e18 0%, #10192b 45%, #080c16 100%);
    color: #e8ecf4;
    font-family: 'Segoe UI', 'Ubuntu', 'Cantarell', 'DejaVu Sans', sans-serif;
}

/* ── Headerbar ── */
headerbar {
    background-color: #0c1424;
    background-image: linear-gradient(to bottom, #142036 0%, #0d1627 100%);
    color: #fce8a6;
    border-bottom: 1px solid rgba(223, 183, 67, 0.35);
    min-height: 38px;
    padding: 0 10px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
}
headerbar .title {
    color: #f7df8d;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-shadow: 0 0 10px rgba(247, 223, 141, 0.35);
}

/* ── Action Bar (Bottom Button Container) ── */
.dialog-action-area {
    background-color: #090f1a;
    background-image: linear-gradient(to bottom, #111a2c 0%, #090e18 100%);
    border-top: 1px solid rgba(223, 183, 67, 0.22);
    padding: 16px 24px;
    margin: 0;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.35);
}

/* ── PRIMARY BUTTON (First Child = 🎮 CHƠI GAME) ── */
.dialog-action-area button:first-child {
    background-image: linear-gradient(135deg, #ffe58f 0%, #e5b948 25%, #c28b18 55%, #fadc69 85%, #ffeaa7 100%);
    color: #090d14;
    font-weight: 900;
    font-size: 14px;
    letter-spacing: 3px;
    min-width: 220px;
    min-height: 48px;
    border: 1px solid rgba(255, 240, 180, 0.7);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(229, 185, 72, 0.45),
                0 0 14px rgba(255, 215, 0, 0.3),
                inset 0 1px 1px rgba(255, 255, 255, 0.65);
    text-shadow: 0 1px 0 rgba(255, 255, 255, 0.4);
    padding: 0 32px;
    margin-right: 14px;
    transition: all 220ms cubic-bezier(0.4, 0, 0.2, 1);
}
.dialog-action-area button:first-child:hover {
    background-image: linear-gradient(135deg, #fff1b8 0%, #f5cf65 25%, #d49e24 55%, #ffe58f 85%, #fffbe6 100%);
    box-shadow: 0 6px 28px rgba(255, 215, 0, 0.65),
                0 0 22px rgba(229, 185, 72, 0.55),
                inset 0 1px 2px rgba(255, 255, 255, 0.85);
    border-color: rgba(255, 250, 220, 0.95);
    transform: translateY(-1px);
}
.dialog-action-area button:first-child:active {
    background-image: linear-gradient(135deg, #b8860b 0%, #8b6508 55%, #b8860b 100%);
    box-shadow: 0 2px 10px rgba(200, 150, 30, 0.35);
    transform: translateY(1px);
}

/* ── SECONDARY BUTTONS (Update, Menu, Cancel) ── */
.dialog-action-area button:not(:first-child) {
    background-color: #121c2e;
    background-image: linear-gradient(to bottom, #17243b 0%, #0f1828 100%);
    color: #cad8ee;
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 8px;
    font-weight: 700;
    font-size: 12.5px;
    letter-spacing: 0.5px;
    min-height: 44px;
    padding: 0 20px;
    margin: 0 4px;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3);
    transition: all 180ms ease;
}
.dialog-action-area button:not(:first-child):hover {
    background-image: linear-gradient(to bottom, #203252 0%, #15233a 100%);
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.65);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4),
                0 0 12px rgba(56, 189, 248, 0.28);
    transform: translateY(-1px);
}
.dialog-action-area button:not(:first-child):active {
    background-image: linear-gradient(to bottom, #0f1828 0%, #090e18 100%);
    transform: translateY(1px);
}

/* ── General Buttons ── */
button {
    background-color: #141f33;
    background-image: linear-gradient(to bottom, #19273f 0%, #111a2c 100%);
    color: #dce5f2;
    border: 1px solid rgba(223, 183, 67, 0.25);
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 700;
    min-height: 36px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    transition: all 180ms ease;
}
button:hover {
    background-image: linear-gradient(to bottom, #233555 0%, #16243d 100%);
    border-color: rgba(247, 223, 141, 0.55);
    color: #f7df8d;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.35),
                0 0 10px rgba(223, 183, 67, 0.22);
}
button:active, button:checked {
    background-image: linear-gradient(to bottom, #d4af37 0%, #997312 100%);
    color: #0b0f19;
}

/* ── Entries, Textviews ── */
entry, textview, textview text {
    background-color: #0e1624;
    color: #e4edf8;
    border: 1px solid rgba(56, 189, 248, 0.22);
    border-radius: 6px;
    padding: 8px 12px;
}
entry:focus {
    border-color: rgba(56, 189, 248, 0.7);
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
}

/* ── Treeview / List (Secondary Menu) ── */
treeview {
    background-color: #0d1522;
    color: #dce5f2;
    border: 1px solid rgba(223, 183, 67, 0.18);
    border-radius: 8px;
    padding: 4px;
}
treeview:selected, treeview row:selected {
    background-color: rgba(223, 183, 67, 0.25);
    color: #ffe58f;
    font-weight: 700;
}
treeview row:hover {
    background-color: rgba(56, 189, 248, 0.12);
}
treeview header button {
    background-image: linear-gradient(to bottom, #16233a 0%, #0f192b 100%);
    color: #f5d77f;
    border-bottom: 1px solid rgba(223, 183, 67, 0.35);
    font-weight: 800;
    font-size: 11.5px;
    letter-spacing: 1px;
}

/* ── Progress Bar (Premium Animated) ── */
@keyframes progress-stripes {
    0%   { background-position: 0 0; }
    100% { background-position: 40px 0; }
}
@keyframes progress-glow {
    0%, 100% { box-shadow: 0 0 12px rgba(56, 189, 248, 0.5), 0 0 6px rgba(253, 224, 71, 0.3); }
    50%      { box-shadow: 0 0 22px rgba(56, 189, 248, 0.8), 0 0 12px rgba(253, 224, 71, 0.55), 0 0 40px rgba(56, 189, 248, 0.25); }
}
progressbar {
    padding: 0;
    margin: 6px 0;
}
progressbar trough {
    background-color: #060b14;
    background-image: linear-gradient(to bottom, #080d18 0%, #0a1020 50%, #060b14 100%);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 12px;
    min-height: 26px;
    box-shadow: inset 0 3px 8px rgba(0, 0, 0, 0.7),
                inset 0 1px 2px rgba(0, 0, 0, 0.5),
                0 1px 0 rgba(255, 255, 255, 0.03);
    padding: 3px;
}
progressbar progress {
    background-image:
        linear-gradient(
            -45deg,
            rgba(255, 255, 255, 0.12) 25%,
            transparent 25%,
            transparent 50%,
            rgba(255, 255, 255, 0.12) 50%,
            rgba(255, 255, 255, 0.12) 75%,
            transparent 75%,
            transparent
        ),
        linear-gradient(90deg, #0369a1 0%, #0ea5e9 20%, #38bdf8 40%, #eab308 70%, #fde047 90%, #fef08a 100%);
    background-size: 40px 40px, 100% 100%;
    border-radius: 10px;
    min-height: 20px;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.55),
                0 0 6px rgba(253, 224, 71, 0.4),
                inset 0 1px 1px rgba(255, 255, 255, 0.25),
                inset 0 -1px 1px rgba(0, 0, 0, 0.2);
    animation: progress-stripes 1.2s linear infinite,
               progress-glow 2.4s ease-in-out infinite;
    transition: min-width 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
progressbar text {
    color: #ffffff;
    font-weight: 800;
    font-size: 11px;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
    letter-spacing: 1px;
}

/* ── Labels & Text ── */
label {
    color: #e4edf8;
}

/* ── Separators & Scrollbars ── */
separator {
    background-color: rgba(223, 183, 67, 0.15);
    min-height: 1px;
}
scrollbar {
    background-color: transparent;
}
scrollbar slider {
    background-color: rgba(223, 183, 67, 0.25);
    border-radius: 8px;
    min-width: 7px;
    min-height: 40px;
    border: 1px solid rgba(223, 183, 67, 0.1);
    transition: background-color 200ms ease;
}
scrollbar slider:hover {
    background-color: rgba(223, 183, 67, 0.45);
}

/* ── Tooltip ── */
tooltip, tooltip.background {
    background-color: #0c1424;
    color: #e4edf8;
    border: 1px solid rgba(223, 183, 67, 0.3);
    border-radius: 8px;
    padding: 6px 10px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

/* ── Dialog Image (Rounded Logo with Glow) ── */
#yad-dialog-image, image {
    margin: 10px 18px 10px 4px;
    border-radius: 22px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55),
                0 0 18px rgba(223, 183, 67, 0.35),
                0 0 40px rgba(223, 183, 67, 0.12);
}

/* ── Notebook / Tabs (if used) ── */
notebook tab {
    background-color: #0d1522;
    color: #94a3b8;
    border: 1px solid rgba(223, 183, 67, 0.15);
    border-radius: 6px 6px 0 0;
    padding: 6px 14px;
}
notebook tab:checked {
    background-color: #141f33;
    color: #f5d77f;
    border-bottom-color: transparent;
}
CSSEOF

    if [ -f "$CSS_FILE" ]; then
        USE_CUSTOM_CSS=true
        log "Theme CSS GTK3 cao cấp (Celestial Obsidian & Gold) đã được kích hoạt"
    fi

    trap 'rm -f "$CSS_FILE" 2>/dev/null' EXIT
}

# ── YAD wrapper that applies theme ────────────────────────────────────────────
yad_themed() {
    if $USE_CUSTOM_CSS && [ -f "$CSS_FILE" ]; then
        yad --gtkrc="$CSS_FILE" "$@" 2>/dev/null
    else
        yad "$@" 2>/dev/null
    fi
}

# ── Prepare Rounded Logo for GUI ──────────────────────────────────────────────
ROUNDED_ICON_PATH=""

prepare_rounded_logo() {
    [ -n "$ICON_PATH" ] && [ -f "$ICON_PATH" ] || return 0
    ROUNDED_ICON_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/wuwavh/wuwavh-rounded.png"
    mkdir -p "$(dirname "$ROUNDED_ICON_PATH")"

    if [ ! -f "$ROUNDED_ICON_PATH" ] || [ "$ICON_PATH" -nt "$ROUNDED_ICON_PATH" ]; then
        if command -v python3 &>/dev/null; then
            python3 -c '
from PIL import Image, ImageDraw
import sys

src = sys.argv[1]
dst = sys.argv[2]
try:
    im = Image.open(src).convert("RGBA")
    size = (110, 110)
    im = im.resize(size, Image.Resampling.LANCZOS)

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=22, fill=255)

    rounded = Image.new("RGBA", size, (0, 0, 0, 0))
    rounded.paste(im, (0, 0), mask=mask)

    border_draw = ImageDraw.Draw(rounded)
    border_draw.rounded_rectangle([(0, 0), (size[0]-1, size[1]-1)], radius=22, outline=(223, 183, 67, 220), width=2)

    rounded.save(dst, "PNG")
except Exception:
    sys.exit(1)
' "$ICON_PATH" "$ROUNDED_ICON_PATH" 2>/dev/null || cp -f "$ICON_PATH" "$ROUNDED_ICON_PATH" 2>/dev/null
        else
            cp -f "$ICON_PATH" "$ROUNDED_ICON_PATH" 2>/dev/null
        fi
    fi

    [ -f "$ROUNDED_ICON_PATH" ] || ROUNDED_ICON_PATH="$ICON_PATH"
}

# ── Print Terminal Image Logo ─────────────────────────────────────────────────
print_terminal_banner() {
    local img="${ICON_PATH:-$SCRIPT_DIR/wuwavh.png}"
    if [ -f "$img" ]; then
        if command -v chafa &>/dev/null; then
            echo ""
            chafa -s 32x15 --symbols=block,braille "$img" 2>/dev/null || true
            echo ""
        fi
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

load_config() {
    [ -f "$CONFIG_PATH" ] && cat "$CONFIG_PATH" 2>/dev/null || echo "{}"
}

get_config_val() {
    load_config | jq -r ".${1} // empty" 2>/dev/null
}

set_config_val() {
    mkdir -p "$(dirname "$CONFIG_PATH")"
    local cfg
    cfg=$(load_config)
    echo "$cfg" | jq --arg k "$1" --arg v "$2" '. + {($k): $v}' > "$CONFIG_PATH" 2>/dev/null
}

# ══════════════════════════════════════════════════════════════════════════════
#  GAME DETECTION
# ══════════════════════════════════════════════════════════════════════════════

detect_game_path() {
    # 1) Check saved config
    local cfg_path
    cfg_path=$(get_config_val game_path)
    if [ -n "$cfg_path" ] && [ -d "$cfg_path" ]; then
        echo "$cfg_path"; return 0
    fi

    # 2) Check well-known locations
    for p in "${DEFAULT_SEARCH_PATHS[@]}"; do
        if [ -d "$p" ]; then
            echo "$p"; return 0
        fi
    done

    # 3) Parse Steam library folders
    local sf
    for sf in "$HOME/.steam/steam/steamapps/libraryfolders.vdf" \
              "$HOME/.local/share/Steam/steamapps/libraryfolders.vdf" \
              "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/libraryfolders.vdf" \
              "$HOME/.var/app/com.valvesoftware.Steam/.steam/steam/steamapps/libraryfolders.vdf"; do
        [ -f "$sf" ] || continue
        while IFS= read -r line; do
            if [[ "$line" == *'"path"'* ]]; then
                local lib_path
                lib_path=$(echo "$line" | grep -oP '"path"\s+"\K[^"]+')
                local candidate="$lib_path/steamapps/common/Wuthering Waves"
                if [ -d "$candidate" ]; then
                    echo "$candidate"; return 0
                fi
            fi
        done < "$sf"
    done

    return 1
}

get_game_exe() {
    local gp
    gp=$(detect_game_path) || return 1
    find "$gp" -name "$GAME_EXE_NAME" -type f 2>/dev/null | head -1
}

get_pak_dir() {
    local gp
    gp=$(detect_game_path) || return 1
    echo "$gp/$PAK_SUBPATH"
}

is_game_running() {
    pgrep -f "Client-Win64-Shipping" &>/dev/null || pgrep -f "WutheringWaves" &>/dev/null
}

# ══════════════════════════════════════════════════════════════════════════════
#  GAME MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

set_game_path()  { set_config_val "game_path"  "$1"; }
get_vh_version() { get_config_val "vh_version"; }
set_vh_version() { set_config_val "vh_version" "$1"; }

install_paks() {
    local game_path
    game_path=$(detect_game_path) || { err "Không tìm thấy thư mục game"; return 1; }

    local pak_dest="$game_path/$PAK_SUBPATH"
    local bin_dest="$game_path/Client/Binaries/Win64"
    mkdir -p "$pak_dest" "$bin_dest"

    local installed=()
    for f in "$PAK_DIR"/*; do
        [ -f "$f" ] || continue
        local name
        name=$(basename "$f")
        case "$name" in
            *.pak|*.utoc|*.ucas)
                cp -f "$f" "$pak_dest/$name" && installed+=("$name")
                ;;
            winhttp.dll)
                cp -f "$f" "$bin_dest/$name" && installed+=("$name")
                ;;
        esac
    done

    if (( ${#installed[@]} )); then
        echo "${installed[*]}"
        return 0
    fi
    return 1
}

uninstall_paks() {
    local game_path
    game_path=$(detect_game_path) || return 1

    local pak_dir="$game_path/$PAK_SUBPATH"
    local bin_dir="$game_path/Client/Binaries/Win64"
    local removed=()

    if [ -d "$pak_dir" ]; then
        while IFS= read -r -d '' f; do
            rm -f "$f" && removed+=("$(basename "$f")")
        done < <(find "$pak_dir" \( -name "*_99_P.pak" -o -name "*_99_P.utoc" -o -name "*_99_P.ucas" \) -print0 2>/dev/null)
    fi

    local dll="$bin_dir/winhttp.dll"
    [ -f "$dll" ] && rm -f "$dll" && removed+=("winhttp.dll")

    set_vh_version ""

    if (( ${#removed[@]} )); then
        echo "${removed[*]}"
        return 0
    fi
    return 1
}

fix_steam_launch_options() {
    local fixed_count=0
    local vdf
    while IFS= read -r -d '' vdf; do
        if grep -q 'winhttp\.dll=n,b' "$vdf" 2>/dev/null; then
            sed -i 's/winhttp\.dll=n,b/winhttp=n,b/g' "$vdf"
            ok "Đã sửa WINEDLLOVERRIDES trong: $vdf"
            fixed_count=$((fixed_count + 1))
        fi
    done < <(find "$HOME/.local/share/Steam/userdata" \
                  "$HOME/.steam/steam/userdata" \
                  "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam/userdata" \
                  "$HOME/.var/app/com.valvesoftware.Steam/.steam/steam/userdata" \
             -name "localconfig.vdf" -print0 2>/dev/null)

    echo "$fixed_count"
}

launch_game() {
    fix_steam_launch_options >/dev/null 2>&1

    local exe
    exe=$(get_game_exe)
    [ -z "$exe" ] && { err "Không tìm thấy game executable"; return 1; }

    # Native binary?
    if [[ "$exe" != *.exe ]]; then
        (cd "$(dirname "$exe")" && exec "$exe") &
        return 0
    fi

    # Steam headless launch
    log "Khởi chạy qua Steam: steam -silent -applaunch $STEAM_APP_ID"
    if command -v steam &>/dev/null; then
        steam -silent -applaunch "$STEAM_APP_ID" &>/dev/null &
        return 0
    fi

    # Flatpak Steam fallback
    if command -v flatpak &>/dev/null && flatpak info com.valvesoftware.Steam &>/dev/null; then
        flatpak run com.valvesoftware.Steam -silent -applaunch "$STEAM_APP_ID" &>/dev/null &
        return 0
    fi

    # Fallback: steam:// URL handler
    if command -v xdg-open &>/dev/null; then
        xdg-open "steam://rungameid/$STEAM_APP_ID" &>/dev/null &
        return 0
    fi

    err "Không tìm thấy Steam trên hệ thống"; return 1
}

force_kill_game() {
    pkill -f "WutheringWaves" 2>/dev/null
    pkill -f "Client-Win64"   2>/dev/null
    ok "Đã gửi tín hiệu dừng toàn bộ tiến trình game"
}

open_game_folder() {
    local gp
    gp=$(detect_game_path) || { err "Không tìm thấy thư mục game"; return 1; }
    xdg-open "$gp" &>/dev/null &
}

# ══════════════════════════════════════════════════════════════════════════════
#  CRYPTO — HMAC-SHA256 SIGNING
# ══════════════════════════════════════════════════════════════════════════════

compute_hmac_key() {
    local hex=""
    for i in "${!MASK_BYTES[@]}"; do
        local xor=$(( DATA_BYTES[i] ^ MASK_BYTES[i] ))
        hex+=$(printf '%02x' "$xor")
    done
    HMAC_KEY_HEX="$hex"
    log "Khởi tạo khóa xác thực HMAC (${#HMAC_KEY_HEX} hex chars)"
}

get_self_hash() {
    local exe_path="$SCRIPT_DIR/../WuwaClient/DangDevVH.exe"
    [ -f "$exe_path" ] && sha256sum "$exe_path" 2>/dev/null | cut -d' ' -f1
}

sign_request() {
    local body="$1"
    local ts nonce msg sig

    ts=$(date +%s)
    nonce=$(openssl rand -base64 16 | tr '+/' '-_' | tr -d '=')
    msg=$(printf '%s\n%s\n%s' "$ts" "$nonce" "$body")
    sig=$(printf '%s' "$msg" \
        | openssl dgst -sha256 -mac HMAC -macopt "hexkey:$HMAC_KEY_HEX" -binary 2>/dev/null \
        | base64 | tr '+/' '-_' | tr -d '=')

    printf '%s|%s|%s' "$ts" "$nonce" "$sig"
}

mint_href() {
    local provider="$1" version="${2:-}"
    local body

    if [ -n "$version" ]; then
        body="{\"box\":\"$PROXY_BOX\",\"provider\":\"$provider\",\"version\":\"$version\"}"
    else
        body="{\"box\":\"$PROXY_BOX\",\"provider\":\"$provider\"}"
    fi

    local auth ts nonce sig
    auth=$(sign_request "$body")
    IFS='|' read -r ts nonce sig <<< "$auth"

    local self_hash
    self_hash=$(get_self_hash)

    local curl_args=(
        curl -s -X POST "$MINT_URL"
        -H "Content-Type: application/json"
        -H "X-Client-Platform: windows"
        -H "User-Agent: DangDevVH/1.8.3"
        -H "X-Auth-Timestamp: $ts"
        -H "X-Auth-Nonce: $nonce"
        -H "X-Auth-Signature: $sig"
    )
    [ -n "$self_hash" ] && curl_args+=(-H "X-Client-Hash: $self_hash")
    curl_args+=(-d "$body" --max-time 15)

    local response href
    response=$("${curl_args[@]}" 2>/dev/null) || { err "Không kết nối được server xác thực"; return 1; }
    href=$(echo "$response" | jq -r '.href // empty' 2>/dev/null)

    if [ -z "$href" ]; then
        err "Server không trả về link tải hợp lệ: $response"
        return 1
    fi
    echo "$href"
}

# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOADER (With Live Speed & ETA)
# ══════════════════════════════════════════════════════════════════════════════

get_version_info() {
    curl -s --max-time 10 "$VERSION_URL" 2>/dev/null
}

sha256_file() {
    sha256sum "$1" 2>/dev/null | cut -d' ' -f1
}

download_file_progress() {
    local url="$1" dest="$2" label="$3" step="$4" total="$5"

    # Probe total size via HEAD request
    local total_bytes
    total_bytes=$(curl -sI -L -H "User-Agent: DangDevVH/1.8.3" "$url" 2>/dev/null \
        | grep -i '^content-length:' | tail -1 | awk '{print $2}' | tr -d '\r\n')
    total_bytes=${total_bytes:-0}

    local total_mb="?"
    (( total_bytes > 0 )) 2>/dev/null && \
        total_mb=$(awk "BEGIN {printf \"%.1f\", $total_bytes / 1048576}")

    # Remove existing partial file
    rm -f "$dest" 2>/dev/null

    # Start download in background, saving response headers to extract Content-Length if HEAD failed
    local header_tmp
    header_tmp=$(mktemp /tmp/wuwavh_hdr.XXXXXX 2>/dev/null || echo "/tmp/wuwavh_hdr_$$")
    curl -L -s -H "User-Agent: DangDevVH/1.8.3" -D "$header_tmp" -o "$dest" "$url" &
    local curl_pid=$!

    # Feed progress to dialog with speed calculation
    (
        trap "kill $curl_pid 2>/dev/null; exit 0" PIPE TERM
        local last_bytes=0
        local last_time
        last_time=$(date +%s)
        local last_pct=-1
        local header_checked=false

        while kill -0 "$curl_pid" 2>/dev/null; do
            # Try to pick up Content-Length from response headers if HEAD failed
            if ! $header_checked && (( total_bytes <= 0 )) && [ -f "$header_tmp" ]; then
                local cl
                cl=$(grep -i '^content-length:' "$header_tmp" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d '\r\n')
                if [ -n "$cl" ] && (( cl > 0 )) 2>/dev/null; then
                    total_bytes=$cl
                    total_mb=$(awk "BEGIN {printf \"%.1f\", $total_bytes / 1048576}")
                fi
                header_checked=true
            fi

            if [ -f "$dest" ]; then
                local current current_time dt db speed_str eta_str
                current=$(stat -c%s "$dest" 2>/dev/null || echo 0)
                current_time=$(date +%s)
                dt=$(( current_time - last_time ))

                if (( dt >= 1 )); then
                    db=$(( current - last_bytes ))
                    local speed_kb=$(( db / dt / 1024 ))
                    if (( speed_kb > 1024 )); then
                        speed_str=$(awk "BEGIN {printf \"%.1f MB/s\", $speed_kb / 1024}")
                    else
                        speed_str="${speed_kb} KB/s"
                    fi

                    if (( total_bytes > 0 && db > 0 )); then
                        local remain_bytes=$(( total_bytes - current ))
                        local eta_sec=$(( remain_bytes / (db / dt + 1) ))
                        if (( eta_sec > 60 )); then
                            eta_str="$(( eta_sec / 60 ))m $(( eta_sec % 60 ))s"
                        else
                            eta_str="${eta_sec}s"
                        fi
                    else
                        eta_str="--"
                    fi

                    last_bytes=$current
                    last_time=$current_time
                fi

                speed_str="${speed_str:-Đang tính...}"
                eta_str="${eta_str:-...}"

                if (( total_bytes > 0 )) 2>/dev/null; then
                    local pct=$(( current * 100 / total_bytes ))
                    (( pct > 100 )) && pct=100
                    local done_mb
                    done_mb=$(awk "BEGIN {printf \"%.1f\", $current / 1048576}")
                    echo "$pct"
                    echo "# ⬇ [$step/$total] $label  —  📦 ${done_mb} / ${total_mb} MB   ·   ⚡ $speed_str   ·   ⏱ $eta_str"
                else
                    local done_mb
                    done_mb=$(awk "BEGIN {printf \"%.1f\", $current / 1048576}")
                    # Fake pulsating progress (bounce 5-95%) so bar is not stuck at 0
                    local fake_pct=$(( (current / 1048576 * 3) % 91 + 5 ))
                    (( fake_pct > 95 )) && fake_pct=95
                    echo "$fake_pct"
                    echo "# ⬇ [$step/$total] $label  —  📦 ${done_mb} MB đã tải   ·   ⚡ $speed_str"
                fi
            fi
            sleep 0.5
        done
        echo "100"
        echo "# ✅ Hoàn tất tải [$step/$total] $label"
        sleep 0.3
    ) | gui_progress_dialog "⬇  Tải Bản Dịch Việt Hoá" "Đang khởi tạo kết nối tải $label..."
    rm -f "$header_tmp" 2>/dev/null

    # If curl is still alive, the user cancelled the dialog
    if kill -0 "$curl_pid" 2>/dev/null; then
        kill "$curl_pid" 2>/dev/null
        wait "$curl_pid" 2>/dev/null
        rm -f "$dest" 2>/dev/null
        warn "Người dùng đã hủy quá trình tải: $label"
        return 1
    fi

    wait "$curl_pid" 2>/dev/null
    local ret=$?

    # Verify file existence and non-zero size
    if [ ! -f "$dest" ] || [ ! -s "$dest" ]; then
        err "File tải về không hợp lệ hoặc bị rỗng: $label"
        return 1
    fi
    return $ret
}

# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE VH FLOW
# ══════════════════════════════════════════════════════════════════════════════

do_update_vh() {
    mkdir -p "$PAK_DIR"

    log "Đang kiểm tra thông tin phiên bản từ máy chủ..."
    local ver_json
    ver_json=$(get_version_info) || {
        gui_error "Không thể kết nối đến máy chủ cập nhật.\nVui lòng kiểm tra kết nối mạng Internet."
        return 1
    }

    local version
    version=$(echo "$ver_json" | jq -r '.version // empty' 2>/dev/null)
    if [ -z "$version" ]; then
        gui_error "Dữ liệu phiên bản từ máy chủ không hợp lệ."
        return 1
    fi
    log "Phiên bản mới nhất trên máy chủ: v$version"

    local total=${#PROVIDERS[@]}
    local step=0

    for entry in "${PROVIDERS[@]}"; do
        IFS='|' read -r provider filename label <<< "$entry"
        step=$((step + 1))
        local dest="$PAK_DIR/$filename"
        local url

        if [ "$provider" = "raw" ]; then
            url="https://huggingface.co/datasets/BachMacThanh/DangDevVH/resolve/main/Wuwa/dlls/${filename}?download=true"
        else
            log "Tạo chữ ký bảo mật & liên kết tải: $label..."
            url=$(mint_href "$provider" "$version") || {
                gui_error "Không thể lấy liên kết tải bảo mật cho:\n<b>$label</b>"
                return 1
            }
        fi

        log "Bắt đầu tải [$step/$total] $label"
        download_file_progress "$url" "$dest" "$label" "$step" "$total" || {
            gui_error "Quá trình tải thất bại:\n<b>$label</b>"
            return 1
        }

        local sha
        sha=$(sha256_file "$dest")
        ok "$label — SHA256: ${sha:0:16}..."
    done

    # Auto-install
    log "Đang tự động cài đặt các tệp Việt Hoá vào game..."
    local installed
    installed=$(install_paks 2>/dev/null) || true
    if [ -n "$installed" ]; then
        set_vh_version "$version"
        ok "Cập nhật thành công phiên bản: v$version"
        gui_info "🎉 <b>CẬP NHẬT VIỆT HOÁ THÀNH CÔNG!</b>\n\n<span color='#ffd700'><b>Phiên bản:</b></span> v$version\n<span color='#38bdf8'><b>Tệp đã áp dụng:</b></span>\n$installed\n\n<i>Bạn có thể khởi chạy game ngay bây giờ!</i>"
    else
        gui_error "Tải tệp thành công nhưng chưa thể cài vào thư mục game.\nVui lòng mở <b>Menu ➔ Chọn thư mục game</b> rồi thử lại."
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
#  INTEGRITY VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

verify_integrity() {
    local game_path
    game_path=$(detect_game_path 2>/dev/null) || {
        gui_error "Chưa thiết lập thư mục game để kiểm tra."
        return 1
    }

    local pd="$game_path/$PAK_SUBPATH"
    local bin_dir="$game_path/Client/Binaries/Win64"
    local report="<b>✦ BÁO CÁO TÍNH TOÀN VẸN TỆP VIỆT HOÁ ✦</b>\n\n"
    report+="<b>Thư mục game:</b> <span color='#38bdf8'>$game_path</span>\n\n"

    local total_found=0
    if [ -d "$pd" ]; then
        report+="<b>Tệp Pak trong game:</b>\n"
        while IFS= read -r f; do
            [ -f "$f" ] || continue
            local name sha size_kb
            name=$(basename "$f")
            sha=$(sha256_file "$f")
            size_kb=$(stat -c%s "$f" 2>/dev/null | awk '{printf "%.1f MB", $1/1048576}')
            report+=" • <span color='#ffd700'>$name</span> (${size_kb})\n   <span color='#5a6a88'>SHA: ${sha:0:24}...</span>\n"
            total_found=$((total_found + 1))
        done < <(find "$pd" -type f \( -name "*_99_P*" \) 2>/dev/null)
    fi

    if [ -f "$bin_dir/winhttp.dll" ]; then
        local dsha
        dsha=$(sha256_file "$bin_dir/winhttp.dll")
        report+="\n<b>Proxy DLL:</b>\n • <span color='#2ecc71'>winhttp.dll</span> (Đã kích hoạt)\n   <span color='#5a6a88'>SHA: ${dsha:0:24}...</span>\n"
        total_found=$((total_found + 1))
    else
        report+="\n<b>Proxy DLL:</b> <span color='#ef4444'>Chưa tìm thấy winhttp.dll</span>\n"
    fi

    if (( total_found > 0 )); then
        report+="\n<span color='#2ecc71'>✔ Tìm thấy $total_found thành phần Việt Hoá đang hoạt động.</span>"
    else
        report+="\n<span color='#eab308'>⚠ Chưa phát hiện tệp Việt Hoá nào trong thư mục game.</span>"
    fi

    gui_info "$report"
}

# ══════════════════════════════════════════════════════════════════════════════
#  GUI — DIALOGS (YAD / Zenity)
# ══════════════════════════════════════════════════════════════════════════════

gui_info() {
    if $HAS_YAD; then
        local win_icon_arg=()
        [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")
        yad_themed --info \
            --title="WuWaVH — Thông Báo" \
            --text="\n$1\n" \
            --width=460 --center \
            "${win_icon_arg[@]}" \
            --button="  Đồng ý  :0"
    else
        zenity --info --title="WuWaVH" --text="$1" --width=460 2>/dev/null
    fi
}

gui_error() {
    if $HAS_YAD; then
        local win_icon_arg=()
        [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")
        yad_themed --error \
            --title="WuWaVH — Có Lỗi Xảy Ra" \
            --text="\n$1\n" \
            --width=460 --center \
            "${win_icon_arg[@]}" \
            --button="  Đóng  :0"
    else
        zenity --error --title="WuWaVH — Lỗi" --text="$1" --width=460 2>/dev/null
    fi
}

gui_confirm() {
    if $HAS_YAD; then
        local win_icon_arg=()
        [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")
        yad_themed --question \
            --title="WuWaVH — Xác Nhận" \
            --text="\n$1\n" \
            --width=460 --center \
            "${win_icon_arg[@]}" \
            --button="  Huỷ bỏ  :1" --button="  Xác nhận  :0"
        return $?
    else
        zenity --question --title="WuWaVH" --text="$1" --width=460 2>/dev/null
        return $?
    fi
}

gui_progress_dialog() {
    local win_icon_arg=()
    [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")
    if $HAS_YAD; then
        yad_themed --progress \
            --title="$1" \
            --text="$2" \
            --width=580 --height=160 --center \
            --auto-close \
            --auto-kill \
            --no-buttons \
            --borders=20 \
            "${win_icon_arg[@]}"
    else
        zenity --progress \
            --title="$1" \
            --text="$2" \
            --width=580 \
            --auto-close 2>/dev/null
    fi
}

gui_ask_path() {
    local result
    local win_icon_arg=()
    [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")
    if $HAS_YAD; then
        result=$(yad_themed --file \
            --directory \
            --title="Chọn Thư Mục Cài Đặt Wuthering Waves" \
            --width=680 --height=480 --center \
            "${win_icon_arg[@]}")
        [ $? -eq 0 ] && [ -n "$result" ] && [ -d "$result" ] && { echo "$result"; return 0; }
    else
        result=$(zenity --file-selection --directory \
            --title="Chọn Thư Mục Cài Đặt Wuthering Waves" 2>/dev/null)
        [ $? -eq 0 ] && [ -n "$result" ] && [ -d "$result" ] && { echo "$result"; return 0; }
    fi
    return 1
}

# ══════════════════════════════════════════════════════════════════════════════
#  GUI — CONTROL CENTER MENU
# ══════════════════════════════════════════════════════════════════════════════

show_more_menu() {
    local choice
    local win_icon_arg=()
    [ -n "$ICON_PATH" ] && win_icon_arg=(--window-icon="$ICON_PATH")

    if $HAS_YAD; then
        choice=$(yad_themed --list \
            --title="WuWaVH — Trung Tâm Điều Khiển" \
            --text="\n  <b><span color='#ffd700' size='13500'>✦ MENU QUẢN LÝ & CÀI ĐẶT NÂNG CAO ✦</span></b>\n  <span color='#6a7a98' size='9500'>Chọn một thao tác bên dưới để thực thi</span>\n" \
            --column="Icon":TEXT --column="Hành động":TEXT --column="Mô tả":TEXT \
            --no-headers \
            "🎮" "Khởi chạy game" "Khởi chạy Wuthering Waves qua Steam" \
            "⬇" "Cập nhật Việt Hoá" "Tải phiên bản bản dịch mới nhất từ server" \
            "⚙" "Cài đặt vào game" "Sao chép các file mod .pak vào thư mục game" \
            "📁" "Mở thư mục game" "Mở thư mục cài game trong trình duyệt file" \
            "📂" "Chọn thư mục game" "Tùy chọn đường dẫn cài game thủ công" \
            "🛠" "Sửa lỗi Steam DLL" "Tự động cấu hình WINEDLLOVERRIDES cho Steam" \
            "🔍" "Kiểm tra toàn vẹn" "Quét tệp mod và kiểm tra mã băm SHA256" \
            "🛑" "Buộc dừng game" "Tắt cưỡng bức tất cả tiến trình game đang chạy" \
            "🗑" "Gỡ cài đặt Việt Hoá" "Xóa sạch toàn bộ tệp mod .pak khỏi game" \
            --width=560 --height=440 --center \
            --borders=10 \
            "${win_icon_arg[@]}" \
            --button="  Đóng  :1" --button="  Thực hiện  :0" \
            --print-column=2)
        [ $? -ne 0 ] && return
    else
        choice=$(zenity --list \
            --title="WuWaVH — Menu Quản Lý" \
            --column="Hành động" \
            "Khởi chạy game" \
            "Cập nhật Việt Hoá" \
            "Cài đặt vào game" \
            "Mở thư mục game" \
            "Chọn thư mục game" \
            "Sửa lỗi Steam DLL" \
            "Kiểm tra toàn vẹn" \
            "Buộc dừng game" \
            "Gỡ cài đặt Việt Hoá" \
            --width=450 --height=400 2>/dev/null)
        [ $? -ne 0 ] && return
    fi

    # Strip trailing pipe from YAD output
    choice="${choice%|}"
    choice="$(echo "$choice" | xargs)"

    case "$choice" in
        "Khởi chạy game")
            if launch_game; then
                gui_info "🎮 <b>Game đã được khởi động qua Steam!</b>\nChúc bạn có những giờ phút phiêu lưu tuyệt vời!"
            else
                gui_error "Không thể khởi động game.\nVui lòng kiểm tra lại Steam."
            fi
            ;;

        "Cập nhật Việt Hoá")
            do_update_vh
            refresh_version_cache
            ;;

        "Cài đặt vào game")
            if [ -z "$(detect_game_path 2>/dev/null)" ]; then
                gui_error "Chưa tìm thấy thư mục game.\nHãy chọn đường dẫn game trước."
                return
            fi
            local installed
            installed=$(install_paks 2>/dev/null) || true
            if [ -n "$installed" ]; then
                gui_info "✔ <b>Đã cài thành công vào game:</b>\n$installed"
            else
                gui_info "Chưa có file pak sẵn sàng.\nHãy nhấn \"Cập nhật Việt Hoá\" để tải file trước."
            fi
            ;;

        "Mở thư mục game")
            if ! open_game_folder 2>/dev/null; then
                gui_error "Không tìm thấy thư mục game để mở."
            fi
            ;;

        "Chọn thư mục game")
            local new_path
            new_path=$(gui_ask_path) || return
            if [ -d "$new_path" ]; then
                set_game_path "$new_path"
                gui_info "✔ <b>Đã lưu đường dẫn game mới:</b>\n<span color='#38bdf8'>$new_path</span>"
                ok "Thư mục game mới: $new_path"
            else
                gui_error "Thư mục bạn vừa chọn không hợp lệ:\n$new_path"
            fi
            ;;

        "Sửa lỗi Steam DLL")
            local fixed
            fixed=$(fix_steam_launch_options)
            if (( fixed > 0 )); then
                gui_info "✔ <b>Đã cấu hình thành công!</b>\nĐã sửa WINEDLLOVERRIDES trong $fixed tệp cấu hình Steam."
            else
                gui_info "ℹ <b>Cấu hình Steam chuẩn!</b>\nKhông phát hiện xung đột WINEDLLOVERRIDES cần sửa."
            fi
            ;;

        "Kiểm tra toàn vẹn")
            verify_integrity
            ;;

        "Buộc dừng game")
            force_kill_game
            gui_info "✔ Đã dừng toàn bộ tiến trình game."
            ;;

        "Gỡ cài đặt Việt Hoá")
            gui_confirm "<b>Bạn có chắc chắn muốn gỡ cài đặt Việt Hoá?</b>\n\nToàn bộ tệp mod .pak và winhttp.dll sẽ bị xóa khỏi thư mục game." || return
            local removed
            removed=$(uninstall_paks 2>/dev/null) || true
            if [ -n "$removed" ]; then
                gui_info "✔ <b>Đã gỡ cài đặt sạch sẽ:</b>\n$removed"
            else
                gui_info "Không tìm thấy tệp Việt Hoá nào trong thư mục game."
            fi
            ;;
    esac
}

# ══════════════════════════════════════════════════════════════════════════════
#  GUI — MAIN DASHBOARD WINDOW
# ══════════════════════════════════════════════════════════════════════════════

_CACHED_VER_JSON=""

refresh_version_cache() {
    _CACHED_VER_JSON=$(get_version_info 2>/dev/null) \
        || _CACHED_VER_JSON='{"version":"?","note":"Không thể kết nối máy chủ","date":""}'
}

show_main_window_yad() {
    # ── Gather current state ──
    local game_path
    game_path=$(detect_game_path 2>/dev/null) || game_path=""

    [ -z "$_CACHED_VER_JSON" ] && refresh_version_cache

    local version note date vh_version
    version=$(echo "$_CACHED_VER_JSON"   | jq -r '.version // "?"'                2>/dev/null)
    note=$(echo "$_CACHED_VER_JSON"      | jq -r '.note // "Không có thông báo mới"' 2>/dev/null)
    date=$(echo "$_CACHED_VER_JSON"      | jq -r '.date // ""'                    2>/dev/null)
    vh_version=$(get_vh_version)

    local status_badge
    if is_game_running; then
        status_badge="<span background='#1b4332' color='#4ade80' weight='bold'>  🟢 GAME ĐANG CHẠY  </span>"
    elif [ -n "$game_path" ]; then
        status_badge="<span background='#172554' color='#60a5fa' weight='bold'>  ⚪ SẴN SÀNG KHỞI CHẠY  </span>"
    else
        status_badge="<span background='#450a0a' color='#f87171' weight='bold'>  🔴 CHƯA TÌM THẤY GAME  </span>"
    fi

    # ── Installed paks count ──
    local paks_info="0 tệp"
    if [ -n "$game_path" ]; then
        local pd="$game_path/$PAK_SUBPATH"
        if [ -d "$pd" ]; then
            local cnt
            cnt=$(find "$pd" -name "*_99_P*" 2>/dev/null | wc -l)
            (( cnt > 0 )) && paks_info="${cnt} tệp mod"
        fi
    fi

    # ── Update Alert Callout ──
    local update_callout=""
    if [ -n "$vh_version" ] && [ "$vh_version" != "$version" ] && [ "$version" != "?" ]; then
        update_callout="\n<span background='#451a03' color='#fde047' weight='bold'>  🔥 ĐÃ CÓ BẢN CẬP NHẬT MỚI: v${vh_version} ➜ v${version} (Nhấn 'Cập nhật VH')  </span>"
    elif [ -z "$vh_version" ] && [ "$version" != "?" ]; then
        update_callout="\n<span background='#1e1b4b' color='#a5b4fc' weight='bold'>  ✦ Chưa cài bản dịch — Hãy nhấn 'Cập nhật VH' để tải ngay  </span>"
    fi

    # ── Escape markup in note ──
    local safe_note
    safe_note=$(echo "$note" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')

    # ── Shorten long game path for display ──
    local display_path="${game_path:-<span color='#f87171'><i>Chưa thiết lập đường dẫn game</i></span>}"
    if [ ${#game_path} -gt 52 ]; then
        display_path="…${game_path: -49}"
    fi

    # ── Build Luxurious Pango Layout ──
    local h=""
    h+="\n"
    # Header Branding
    h+="<span size='28000' weight='heavy' color='#ffd700' letter_spacing='3500'>✦ WUTHERING WAVES ✦</span>\n"
    h+="<span size='11500' weight='bold' color='#dfb743' letter_spacing='5000'>VIỆT HOÁ LAUNCHER</span>   <span size='8500' color='#4a5568' style='italic'>v${LAUNCHER_VERSION}</span>\n"
    h+="\n"

    # Decorative Divider (Double line)
    h+="<span color='#c28b18'>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</span>\n"
    h+="\n"

    # Announcement / Patch Notes Card
    h+="<span color='#f5d77f' weight='bold' size='11500'>📢 THÔNG BÁO TỪ MÁY CHỦ</span>"
    [ -n "$date" ] && h+="   <span size='8500' color='#64748b' style='italic'>$date</span>"
    h+="\n"
    h+="<span color='#cbd5e1' size='10500'>$safe_note</span>\n"
    h+="${update_callout}\n"
    h+="\n"

    # Version & Status Dashboard
    h+="<span color='#1e293b'>────────────────────────────────────────────────────────</span>\n"
    h+="\n"

    # Two-column version display with icons
    h+="<span color='#78889e' size='9000' weight='bold' letter_spacing='800'>📡 PHIÊN BẢN MÁY CHỦ</span>          <span color='#78889e' size='9000' weight='bold' letter_spacing='800'>📦 BẢN DỊCH HIỆN TẠI</span>\n"
    h+="<span color='#22c55e' weight='heavy' size='15000'>v${version}</span>                      "

    if [ -n "$vh_version" ]; then
        if [ "$vh_version" = "$version" ]; then
            h+="<span color='#22c55e' weight='heavy' size='15000'>v${vh_version}</span> <span size='9000' color='#22c55e'>✔</span>"
        else
            h+="<span color='#f59e0b' weight='heavy' size='15000'>v${vh_version}</span> <span size='9000' color='#f59e0b'>⟳</span>"
        fi
        h+=" <span size='8500' color='#64748b'>($paks_info)</span>"
    else
        h+="<span color='#ef4444' weight='bold' size='12000'>✗ Chưa cài đặt</span>"
    fi
    h+="\n\n"

    # System Status & Game Directory (improved spacing)
    h+="<span color='#78889e' size='9000' weight='bold'>TRẠNG THÁI</span>   ${status_badge}\n"
    h+="<span color='#78889e' size='9000' weight='bold'>ĐƯỜNG DẪN</span>    <span color='#94a3b8' size='9500' font_family='monospace'>$display_path</span>\n"
    h+="\n"
    h+="<span color='#c28b18'>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</span>\n"

    local yad_args=(
        --form
        --title="WuWaVH Launcher"
        --width=740 --height=560
        --center
        --borders=28
        --text="$h"
        --text-align=left
        --button="  🎮   CHƠI GAME   :0"
        --button="  ⬇  Cập nhật VH  :2"
        --button="  ⚡  Menu tùy chọn  :6"
    )
    [ -n "$ICON_PATH" ] && yad_args+=(--window-icon="$ICON_PATH")
    [ -n "$ROUNDED_ICON_PATH" ] && [ -f "$ROUNDED_ICON_PATH" ] && yad_args+=(--image="$ROUNDED_ICON_PATH")

    # ── Display Form Window ──
    yad_themed "${yad_args[@]}"
    return $?
}

show_main_window_zenity() {
    local game_path
    game_path=$(detect_game_path 2>/dev/null) || game_path="Chưa tìm thấy"

    [ -z "$_CACHED_VER_JSON" ] && refresh_version_cache

    local version note vh_version status_text
    version=$(echo "$_CACHED_VER_JSON"   | jq -r '.version // "?"'                2>/dev/null)
    note=$(echo "$_CACHED_VER_JSON"      | jq -r '.note // "Không có thông báo"'  2>/dev/null)
    vh_version=$(get_vh_version)

    is_game_running && status_text="🟢 Đang chạy" || status_text="⚪ Sẵn sàng"

    local choice
    choice=$(zenity --list \
        --title="WuWaVH Launcher — v${LAUNCHER_VERSION}" \
        --text="✦ WUTHERING WAVES VIỆT HOÁ LAUNCHER ✦\n\n📢 ${note}\n\n📡 Server: v${version}  |  📦 Đã cài: ${vh_version:-Chưa cài}  |  ${status_text}\n📁 Game: ${game_path}" \
        --column="ID" --column="Hành động" \
        --hide-column=1 --print-column=1 \
        "play"      "🎮  CHƠI GAME (Steam)" \
        "update"    "⬇  Cập nhật / Tải Việt Hoá" \
        "install"   "⚙  Cài đặt vào Game" \
        "folder"    "📁  Mở thư mục game" \
        "path"      "📂  Chọn thư mục game" \
        "fixsteam"  "🛠  Sửa lỗi Steam DLL" \
        "verify"    "🔍  Kiểm tra toàn vẹn tệp" \
        "kill"      "🛑  Buộc dừng game" \
        "uninstall" "🗑  Gỡ cài đặt Việt Hoá" \
        --width=540 --height=480 2>/dev/null)
    local ret=$?

    [ $ret -ne 0 ] && return 252  # window closed
    choice="${choice%|}"
    case "$choice" in
        play)      return 0 ;;
        update)    return 2 ;;
        install)   return 3 ;;
        folder)    return 4 ;;
        path)      return 5 ;;
        fixsteam)  return 7 ;;
        verify)    return 8 ;;
        kill)      return 10 ;;
        uninstall) return 11 ;;
        *)         return 252 ;;
    esac
}

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

main() {
    check_deps
    setup_theme
    compute_hmac_key
    mkdir -p "$PAK_DIR"
    prepare_rounded_logo

    print_terminal_banner
    echo -e "${_BOLD}${_Y}✦ ═══════════════════════════════════════════════════════════════ ✦${_N}"
    echo -e "${_BOLD}${_Y}        WUTHERING WAVES VIỆT HOÁ LAUNCHER — v${LAUNCHER_VERSION}${_N}"
    echo -e "${_BOLD}${_Y}✦ ═══════════════════════════════════════════════════════════════ ✦${_N}"
    log "Thư mục script : $SCRIPT_DIR"
    log "Thư mục paks   : $PAK_DIR"
    log "Tệp cấu hình   : $CONFIG_PATH"
    [ -n "$ICON_PATH" ] && log "Biểu tượng     : $ICON_PATH"

    # Initial game detection
    local auto_path
    auto_path=$(detect_game_path 2>/dev/null) || true
    if [ -n "$auto_path" ]; then
        ok "Đã phát hiện game: $auto_path"
    else
        warn "Chưa phát hiện thư mục game tự động"
    fi

    # Fetch version info once at startup
    refresh_version_cache

    # ── Auto-update check ──
    local server_ver
    server_ver=$(echo "$_CACHED_VER_JSON" | jq -r '.version // empty' 2>/dev/null)
    local local_ver
    local_ver=$(get_vh_version)

    if [ -n "$server_ver" ] && [ "$server_ver" != "?" ] \
       && [ -n "$auto_path" ] \
       && [ -n "$local_ver" ] \
       && [ "$local_ver" != "$server_ver" ]; then
        log "Phát hiện bản cập nhật: v$local_ver ➜ v$server_ver"
        if gui_confirm "<b>ĐÃ CÓ BẢN CẬP NHẬT VIỆT HOÁ MỚI!</b>\n\n<b>Phiên bản hiện tại:</b> v${local_ver}\n<b>Phiên bản mới nhất:</b> <span color='#2ecc71'>v${server_ver}</span>\n\nBạn có muốn tải và cập nhật ngay bây giờ?"; then
            do_update_vh
            refresh_version_cache
        fi
    fi

    # ── GUI Main Loop ──
    while true; do
        local ret
        if $HAS_YAD; then
            show_main_window_yad
            ret=$?
        else
            show_main_window_zenity
            ret=$?
        fi

        case $ret in
            0) # CHƠI GAME
                if [ -z "$(detect_game_path 2>/dev/null)" ]; then
                    local new_path
                    new_path=$(gui_ask_path) || continue
                    set_game_path "$new_path"
                    ok "Đã thiết lập đường dẫn game: $new_path"
                fi
                if launch_game; then
                    ok "Khởi chạy game thành công"
                    gui_info "🎮 <b>Game đã được khởi động qua Steam!</b>\nChúc bạn chơi game vui vẻ!"
                else
                    gui_error "Không thể khởi động game.\n\nVui lòng kiểm tra:\n• Steam đã được bật?\n• Game Wuthering Waves đã cài đặt đúng cách?"
                fi
                ;;

            2) # Cập nhật VH
                do_update_vh
                _CACHED_VER_JSON=""  # force refresh cache
                ;;

            6) # Menu Trung Tâm Điều Khiển (YAD)
                show_more_menu
                ;;

            # ── Zenity menu return codes ──
            3) # Cài vào Game (Zenity)
                if [ -z "$(detect_game_path 2>/dev/null)" ]; then
                    gui_error "Chưa tìm thấy thư mục game."
                    continue
                fi
                local installed
                installed=$(install_paks 2>/dev/null) || true
                if [ -n "$installed" ]; then
                    gui_info "✔ Đã cài vào game:\n$installed"
                else
                    gui_info "Chưa có tệp mod pak.\nHãy cập nhật Việt Hoá trước."
                fi
                ;;
            4)  ! open_game_folder 2>/dev/null && gui_error "Không tìm thấy thư mục game." ;;
            5)
                local new_path
                new_path=$(gui_ask_path) || continue
                [ -d "$new_path" ] && { set_game_path "$new_path"; gui_info "✔ Đã lưu:\n$new_path"; } \
                    || gui_error "Thư mục không hợp lệ."
                ;;
            7)
                local fixed
                fixed=$(fix_steam_launch_options)
                gui_info "✔ Đã quét và cấu hình Steam ($fixed tệp đã xử lý)."
                ;;
            8)
                verify_integrity
                ;;
            10) force_kill_game; gui_info "Đã buộc dừng toàn bộ tiến trình game." ;;
            11)
                gui_confirm "Gỡ cài đặt Việt Hoá?\nToàn bộ tệp .pak sẽ bị xoá khỏi game." || continue
                local removed
                removed=$(uninstall_paks 2>/dev/null) || true
                [ -n "$removed" ] && gui_info "✔ Đã gỡ:\n$removed" \
                    || gui_info "Không tìm thấy tệp Việt Hoá trong game."
                ;;

            252|*) # Window closed / Cancelled
                log "Đóng launcher. Tạm biệt! 👋"
                break
                ;;
        esac
    done
}

main "$@"

/**
 * WuWaVH Launcher — Themes Registry
 * 
 * Để thêm theme mới sau này:
 * 1. Tạo thư mục `frontend/themes/<theme_id>/`
 * 2. Viết file `frontend/themes/<theme_id>/theme.css`
 * 3. Thêm 1 object vào mảng THEMES dưới đây!
 */

const THEMES = [
  {
    id: "classic",
    name: "Cổ Kính",
    subtitle: "Classic Gold HUD",
    description: "Thanh điều hướng topbar cổ điển, viền kim loại vàng hoàng gia và nền xanh navy huyền bí.",
    tag: "Hoàng Gia",
    accentColor: "#f0d89a",
    palette: ["#f0d89a", "#c9a84c", "#050b18"],
    iconSvg: `<svg class="theme-card-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>`,
    css: "themes/classic/theme.css",
    previewGradient: "linear-gradient(135deg, #241b0b 0%, #3d2e10 50%, #081228 100%)",
  },
  {
    id: "modern",
    name: "Hiện Đại",
    subtitle: "Modern Cyber Dock",
    description: "Thanh dock thu gọn bên trái với menu mở rộng, hiệu ứng kính mờ và màu xanh Mint tương lai.",
    tag: "Tối Giản",
    accentColor: "#2dd4bf",
    palette: ["#2dd4bf", "#0d9488", "#0a161f"],
    iconSvg: `<svg class="theme-card-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L4 9l8 13 8-13-8-7zm0 2.5l5.5 4.8H6.5L12 4.5zM6 10.8h4.5l-3.3 5.4-1.2-5.4zm6.5 6.9l-3.2-5.4h6.4l-3.2 5.4zm2-5.4h4.5l-1.2 5.4-3.3-5.4z"/></svg>`,
    css: "themes/modern/theme.css",
    previewGradient: "linear-gradient(135deg, #092625 0%, #0d4a45 50%, #081119 100%)",
  },
  {
    id: "cyber",
    name: "Tương Lai",
    subtitle: "Cyberpunk Crimson HUD",
    description: "Giao diện viễn tưởng Hologram tông Đỏ Neon rực lửa, lưới toạ độ tương lai, viền góc công nghệ và phong cách Cyberpunk uy lực.",
    tag: "Viễn Tưởng",
    accentColor: "#ff1a53",
    palette: ["#ff1a53", "#ff4d6d", "#7b0028"],
    iconSvg: `<svg class="theme-card-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h10M7 12h5M7 17h10"/><circle cx="17" cy="12" r="1.5" fill="currentColor"/></svg>`,
    css: "themes/cyber/theme.css",
    previewGradient: "linear-gradient(135deg, #0d0004 0%, #2e020d 50%, #050002 100%)",
  }
];

if (typeof module !== "undefined" && module.exports) {
  module.exports = { THEMES };
}

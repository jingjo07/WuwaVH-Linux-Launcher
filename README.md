# ✦ WuWaVH Launcher for Linux ✦

> Trình khởi chạy và cài đặt bản dịch Việt Hóa Wuthering Waves trên Linux với giao diện Cyber/Modern/Classic, bộ tải siêu tốc Aria2c đa luồng và công cụ tối ưu đồ họa (Engine.ini).

[![Platform](https://img.shields.io/badge/Platform-Linux%20(Steam%20%7C%20Heroic)-blue.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-WebKitGTK%20%2F%20HTML5%20%2F%20PyQt-orange.svg)](#)

---

## 🌟 Tính Năng Nổi Bật

- 🚀 **Tải Việt Hóa Siêu Tốc (Aria2c Multi-Stream Engine)**:
  - Tích hợp động cơ C++ **Aria2** với 16 kết nối song song, phá bỏ giới hạn bóp băng thông của Cloudflare CDN.
  - Cơ chế **Piece-Splitting (1MB)** triệt tiêu hiện tượng sụt giảm tốc độ ở cuối file (tail latency).
  - Cơ chế **Dự phòng (Dynamic Chunk Work-Stealing)** bằng Python thuần nếu máy chưa có Aria2c.

- 🎨 **Giao Diện Đa Theme (Cyber / Modern / Classic)**:
  - Hiệu ứng kính mờ (Glassmorphism), Cyberpunk HUD, video nền loop mượt mà và nhạc nền tự động phát.
  - Giữ nhạc và video phát liên tục ngay cả khi chuyển cửa sổ hoặc làm việc khác.
  - Tự động tạm dừng media khi vào game để không ảnh hưởng đến âm thanh trong trò chơi.

- ⚡ **Tối Ưu Hiệu Năng Đồ Họa (Performance Tweaker)**:
  - 6 Cấu hình đồ họa chuyên sâu được tinh chỉnh cho Linux / Proton (`Potato`, `Balanced`, `High`, `Ultra`, `Cyber`,...).
  - Tinh chỉnh trực tiếp file `Engine.ini` (Khóa FPS 30/60/90/120, độ phân giải, khử răng cưa, tắt Motion Blur / Hậu kỳ).
  - Tự động sao lưu và khôi phục cài đặt gốc chỉ với 1 click.

- 🔤 **Tùy Biến Font Chữ Trong Game (Font Packer)**:
  - Chuyển đổi và đóng gói trực tiếp các font TrueType (`.ttf`) / OpenType (`.otf`) hoặc file `.pak` thành tệp PAK v12 chuẩn cho Unreal Engine 4.
  - Khôi phục font chữ mặc định của game bất cứ lúc nào.

- 🎮 **Tương Thích Linux Toàn Diện**:
  - Hỗ trợ cả **Steam** (Proton) và **Heroic Games Launcher** (DXVK, VKD3D, Wine Overrides).
  - Tùy chọn kích hoạt chế độ **DirectX 11** (`-dx11`) và biến môi trường C#.
  - Tự động cấu hình `WINEDLLOVERRIDES="winhttp=n,b"` để nạp mod Việt Hóa an toàn.

---

## 📦 Hướng Dẫn Cài Đặt & Khởi Chạy

### Cách 1: Chạy trực tiếp từ AppImage (Khuyên dùng)
Tải file `WuWaVH-Launcher-x86_64.AppImage` từ mục [Releases](https://github.com/jingjo07/WuwaVH-Linux-Launcher/releases):
```bash
chmod +x WuWaVH-Launcher-x86_64.AppImage
./WuWaVH-Launcher-x86_64.AppImage
```

### Cách 2: Chạy trực tiếp từ mã nguồn
Cần cài đặt Python 3, WebKit2GTK và Aria2 trên hệ điều hành của bạn:

**Trên Arch Linux / CachyOS / Manjaro:**
```bash
sudo pacman -S python webkit2gtk-4.1 aria2
```

**Trên Ubuntu / Debian:**
```bash
sudo apt install python3 python3-gi gir1.2-webkit2-4.1 aria2
```

**Khởi chạy launcher:**
```bash
python3 launcher.py
```

---

## 🛠️ Tự Đóng Gói AppImage

Dự án đã tích hợp sẵn script đóng gói tự động bao gồm toàn bộ binary và thư viện phụ thuộc:
```bash
chmod +x build_appimage.sh
./build_appimage.sh
```
File thực thi cuối cùng sẽ xuất hiện tại thư mục gốc: `WuWaVH-Launcher-x86_64.AppImage`.

---

## 📄 Bản Quyền & Lời Cảm Ơn
- Dự án phát triển phục vụ cộng đồng game thủ Wuthering Waves trên Linux.
- Dữ liệu bản dịch Việt Hóa từ cộng đồng DangDevVH.

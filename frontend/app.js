/* ════════════════════════════════════════════════════════════
   WuWaVH Launcher — app.js
   ════════════════════════════════════════════════════════════ */

"use strict";

// ── IPC Bridge ─────────────────────────────────────────────────────────────

const _pending = {};  // id -> {resolve, reject}
let _reqId = 0;

function ipc(action, data = {}) {
  return new Promise((resolve, reject) => {
    if (!window.webkit?.messageHandlers?.backend) {
      reject(new Error("IPC backend not available"));
      return;
    }
    const id = `r${++_reqId}`;
    _pending[id] = { resolve, reject };
    window.webkit.messageHandlers.backend.postMessage(
      { action, data, id }
    );
    // Timeout guard
    setTimeout(() => {
      if (_pending[id]) {
        delete _pending[id];
        reject(new Error(`IPC timeout: ${action}`));
      }
    }, 30_000);
  });
}

// Python calls this to resolve pending promises
window.__resolve = (id, result) => {
  const p = _pending[id];
  if (!p) return;
  delete _pending[id];
  if (result?.error) p.reject(new Error(result.error));
  else p.resolve(result);
};

// Python calls this for events (progress, etc.)
window.__onEvent = (event, data) => {
  switch (event) {
    case "update_progress": onUpdateProgress(data); break;
    case "update_done": onUpdateDone(data); break;
    case "update_error": onUpdateError(data); break;
    case "update_assets_progress": onUpdateAssetsProgress(data); break;
    case "update_assets_done": onUpdateAssetsDone(data); break;
    case "update_assets_error": onUpdateAssetsError(data); break;
    case "launcher_update_progress": onLauncherUpdateProgress(data); break;
    case "launcher_update_engine": onLauncherUpdateEngine(data); break;
    case "launcher_update_done": onLauncherUpdateDone(data); break;
    case "launcher_update_error": onLauncherUpdateError(data); break;
  }
};

// ── Toast ──────────────────────────────────────────────────────────────────

function toast(msg, type = "") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  // Giới hạn tối đa 4 thông báo hiển thị cùng lúc (xóa thông báo cũ nhất nếu vượt quá)
  while (container.children.length >= 4) {
    container.removeChild(container.firstChild);
  }

  const el = document.createElement("div");
  el.className = `toast${type ? " " + type : ""}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    if (el.parentNode === container) {
      el.remove();
    }
  }, 3200);
}

// ── Window controls & Logo Dragging ────────────────────────────────────────

const btnMinimize = document.getElementById("btn-minimize");
if (btnMinimize) {
  btnMinimize.onclick = () => ipc("window_minimize").catch(() => { });
}

const btnClose = document.getElementById("btn-close");
if (btnClose) {
  btnClose.onclick = () => ipc("window_close").catch(() => { });
}

const logoWrap = document.querySelector(".logo-wrap");
if (logoWrap) {
  logoWrap.addEventListener("mousedown", (e) => {
    if (e.button === 0) {
      ipc("window_drag_start", { x: e.screenX, y: e.screenY }).catch(() => { });
    }
  });
}

// ── Version info ───────────────────────────────────────────────────────────

let serverInfo = null;

function updateVhVersionUI() {
  const v = (gameStatus && gameStatus.vh_version) || (serverInfo && serverInfo.version);
  const text = v ? `VH v${v}` : "VH v—";

  const vhClassic = document.getElementById("vh-version");
  if (vhClassic) vhClassic.textContent = text;

  const vhModern = document.getElementById("vh-version-modern");
  if (vhModern) vhModern.textContent = text;

  const vhCyber = document.getElementById("vh-version-cyber");
  if (vhCyber) vhCyber.textContent = text;
}

function updateLauncherVersionUI(ver) {
  const v = ver || (typeof window !== "undefined" ? window.LAUNCHER_VERSION : null);
  if (!v) return;
  const cleanVer = String(v).trim().replace(/^v+/i, "");
  const verStr = `v${cleanVer}`;

  // 1. Cyber Theme: topbar badge and bottom-right tag
  document.querySelectorAll(".cyber-launcher-ver, .cyber-launcher-ver-tag").forEach(el => {
    el.textContent = verStr;
  });

  // 2. Drawer subtitle across all themes
  document.querySelectorAll(".drawer-sub-title").forEach(el => {
    el.textContent = `VIETNAMESE LAUNCHER ${verStr}`;
  });

  // 3. Classic and Modern Themes: footer labels
  document.querySelectorAll(".launcher-ver-lbl").forEach(el => {
    el.textContent = `Launcher ${verStr}`;
  });

  // 4. Generic data attribute targets
  document.querySelectorAll("[data-launcher-ver]").forEach(el => {
    el.textContent = verStr;
  });
  document.querySelectorAll("[data-launcher-ver-lbl]").forEach(el => {
    el.textContent = `Launcher ${verStr}`;
  });
}

let launcherUpdateInfo = null;
let launcherUpdateBusy = false;
let launcherUpdateEngine = "";

async function checkLauncherUpdate(notify = false) {
  const info = await ipc("check_launcher_update");
  launcherUpdateInfo = info;
  const label = document.getElementById("ctx-launcher-update-label");
  if (label) label.textContent = info.available
    ? `Cập nhật Launcher · v${info.latest_version}` : "Cập nhật Launcher";
  if (notify && info.available) toast(`Có Launcher v${info.latest_version} mới. Mở menu để cập nhật.`, "info");
  return info;
}

async function startLauncherUpdate() {
  if (launcherUpdateBusy) return;
  if (modUpdateInProgress || mediaUpdateInProgress) {
    toast("Hãy chờ lượt cập nhật hiện tại hoàn tất.", "info");
    return;
  }
  launcherUpdateBusy = true;
  launcherUpdateEngine = "";
  switchTab("home");
  showUpdateProgress(0, "Đang kiểm tra phiên bản Launcher...");
  try {
    const info = await checkLauncherUpdate();
    if (!info.available) {
      launcherUpdateBusy = false;
      showUpdateProgress(100, "✓ LAUNCHER ĐÃ LÀ PHIÊN BẢN MỚI NHẤT");
      hideUpdateProgress(2500);
      return;
    }
    if (!info.can_install) throw new Error("Bản phát hành không có AppImage hoặc checksum hợp lệ");
    showUpdateProgress(0, `Đang chuẩn bị tải Launcher v${info.latest_version}...`);
    await ipc("install_launcher_update");
  } catch (error) {
    onLauncherUpdateError({ error: error.message });
  }
}

function onLauncherUpdateProgress(data) {
  const pct = data.total ? Math.min(100, Math.round(data.done / data.total * 100)) : 0;
  const engine = launcherUpdateEngine ? ` · ${launcherUpdateEngine}` : "";
  const size = data.total
    ? ` · ${(data.done / 1048576).toFixed(1)} / ${(data.total / 1048576).toFixed(1)} MB`
    : ` · ${(data.done / 1048576).toFixed(1)} MB`;
  showUpdateProgress(pct, `Launcher v${launcherUpdateInfo?.latest_version || "mới"}${engine}${size}`);
}

function onLauncherUpdateEngine(data) {
  launcherUpdateEngine = data.engine === "aria2c" ? "aria2c"
    : data.engine === "dynamic" ? "đa luồng Python" : "urllib";
  showUpdateProgress(0, `Đang tải Launcher bằng ${launcherUpdateEngine}...`);
}

function onLauncherUpdateDone(data) {
  showUpdateProgress(100, `✓ ĐÃ CÀI LAUNCHER v${data.version} · ĐANG KHỞI ĐỘNG LẠI`);
}

function onLauncherUpdateError(data) {
  launcherUpdateBusy = false;
  const error = data.error || "Không thể cập nhật Launcher.";
  showUpdateProgress(0, `❌ Cập nhật Launcher: ${error}`, true);
  toast(`Cập nhật Launcher thất bại: ${error}`, "error");
  hideUpdateProgress(4000);
}

// Immediate initial sync from window.LAUNCHER_VERSION (injected via WebKit or version.js)
if (typeof window !== "undefined" && window.LAUNCHER_VERSION) {
  updateLauncherVersionUI(window.LAUNCHER_VERSION);
}

async function loadVersion() {
  try {
    const info = await ipc("get_version");
    if (info && info.version) {
      serverInfo = info;
      const vText = `v${info.version}`;
      const noteHtml = (info.note || "Không có thông báo.").replace(/\n/g, "<br>");

      // Classic News elements
      const verTag = document.getElementById("ver-tag");
      if (verTag) verTag.textContent = vText;

      const newsDate = document.getElementById("news-date");
      if (newsDate) newsDate.textContent = info.date || "";

      const newsContent = document.getElementById("news-content");
      if (newsContent) newsContent.innerHTML = noteHtml;

      // Modern News elements
      const verTagModern = document.getElementById("ver-tag-modern");
      if (verTagModern) verTagModern.textContent = vText;

      const newsDateModern = document.getElementById("news-date-modern");
      if (newsDateModern) newsDateModern.textContent = info.date || "";

      const newsContentModern = document.getElementById("news-content-modern");
      if (newsContentModern) newsContentModern.innerHTML = noteHtml;

      // Cyber News elements
      const verTagCyber = document.getElementById("ver-tag-cyber");
      if (verTagCyber) verTagCyber.textContent = vText;

      const newsDateCyber = document.getElementById("news-date-cyber");
      if (newsDateCyber) newsDateCyber.textContent = info.date || "";

      const newsContentCyber = document.getElementById("news-content-cyber");
      if (newsContentCyber) newsContentCyber.innerHTML = noteHtml;

      updateVhVersionUI();
    }
  } catch (e) {
    console.error("[loadVersion error]", e);
    const retryMsg = `<span style="color: #ff4d6d;">Không thể tải thông tin phiên bản.</span> &nbsp;<a href="javascript:void(0)" onclick="loadVersion()" style="color: var(--cyan, var(--theme-accent, #ff1a53)); text-decoration: underline; font-size: 11px;">Thử lại ⟳</a>`;
    const newsContent = document.getElementById("news-content");
    if (newsContent) newsContent.innerHTML = retryMsg;
    const newsContentModern = document.getElementById("news-content-modern");
    if (newsContentModern) newsContentModern.innerHTML = retryMsg;
    const newsContentCyber = document.getElementById("news-content-cyber");
    if (newsContentCyber) newsContentCyber.innerHTML = retryMsg;
  }
}

// ── Status check ───────────────────────────────────────────────────────────

let gameStatus = {};
let launcherInfo = { current: "steam" };
let isDx11Enabled = true;
let isCSharpEnvEnabled = true;

function updateLaunchOptionsUI() {
  const dx11Modern = document.getElementById("toggle-dx11-modern");
  const dx11Classic = document.getElementById("toggle-dx11-classic");
  const dx11Cyber = document.getElementById("toggle-dx11-cyber");

  const csharpModern = document.getElementById("toggle-csharp-modern");
  const csharpClassic = document.getElementById("toggle-csharp-classic");
  const csharpCyber = document.getElementById("toggle-csharp-cyber");

  if (dx11Modern) dx11Modern.classList.toggle("active", isDx11Enabled);
  if (dx11Modern) dx11Modern.setAttribute("aria-checked", String(isDx11Enabled));
  if (dx11Classic) dx11Classic.classList.toggle("active", isDx11Enabled);
  if (dx11Cyber) {
    dx11Cyber.classList.toggle("active", isDx11Enabled);
    dx11Cyber.setAttribute("aria-checked", String(isDx11Enabled));
    const knob = dx11Cyber.querySelector(".neon-toggle");
    if (knob) knob.classList.toggle("on", isDx11Enabled);
  }

  if (csharpModern) csharpModern.classList.toggle("active", isCSharpEnvEnabled);
  if (csharpModern) csharpModern.setAttribute("aria-checked", String(isCSharpEnvEnabled));
  if (csharpClassic) csharpClassic.classList.toggle("active", isCSharpEnvEnabled);
  if (csharpCyber) {
    csharpCyber.classList.toggle("active", isCSharpEnvEnabled);
    csharpCyber.setAttribute("aria-checked", String(isCSharpEnvEnabled));
    const knob = csharpCyber.querySelector(".neon-toggle");
    if (knob) knob.classList.toggle("on", isCSharpEnvEnabled);
  }
}

async function toggleDx11(e) {
  if (e) e.stopPropagation();
  const previous = isDx11Enabled;
  isDx11Enabled = !isDx11Enabled;
  updateLaunchOptionsUI();
  try {
    const res = await ipc("set_dx11_mode", { enabled: isDx11Enabled });
    if (res.use_dx11 !== undefined) isDx11Enabled = Boolean(res.use_dx11);
    updateLaunchOptionsUI();
    toast(isDx11Enabled ? "Đã bật DirectX 11 (DXVK)" : "Đã tắt DirectX 11 (Dùng mặc định DX12)", "success");
  } catch (err) {
    isDx11Enabled = previous;
    updateLaunchOptionsUI();
    toast(`Lỗi đổi DirectX 11: ${err.message}`, "error");
  }
}

async function toggleCSharpEnv(e) {
  if (e) e.stopPropagation();
  const previous = isCSharpEnvEnabled;
  isCSharpEnvEnabled = !isCSharpEnvEnabled;
  updateLaunchOptionsUI();
  try {
    const res = await ipc("set_csharp_env_mode", { enabled: isCSharpEnvEnabled });
    if (res.use_csharp_env !== undefined) isCSharpEnvEnabled = Boolean(res.use_csharp_env);
    updateLaunchOptionsUI();
    toast(isCSharpEnvEnabled ? "Đã bật CSharp (-ForceEnableCSharpEnvironment)" : "Đã tắt CSharp", "success");
  } catch (err) {
    isCSharpEnvEnabled = previous;
    updateLaunchOptionsUI();
    toast(`Lỗi đổi CSharp: ${err.message}`, "error");
  }
}

async function refreshStatus() {
  try {
    gameStatus = await ipc("get_status");
    if (gameStatus.launcher_info) {
      launcherInfo = gameStatus.launcher_info;
    }
    if (gameStatus.use_dx11 !== undefined) {
      isDx11Enabled = Boolean(gameStatus.use_dx11);
    }
    if (gameStatus.use_csharp_env !== undefined) {
      isCSharpEnvEnabled = Boolean(gameStatus.use_csharp_env);
    }
    updateLaunchOptionsUI();
    updatePlayBtn();
    updateModernStatus();
    updateLauncherBadge();
    updateVhVersionUI();
    if (gameStatus.launcher_version) {
      updateLauncherVersionUI(gameStatus.launcher_version);
    }

    // Auto-pause background video when game is actively running
    if (gameStatus.game_running) {
      if (window._pauseBgMedia) window._pauseBgMedia();
    } else {
      if (window._resumeBgMedia) window._resumeBgMedia();
    }
  } catch (e) {
    console.warn("[Status Refresh Error]", e);
  }
}

function updateModernStatus() {
  const card = document.querySelector(".modern-status-card");
  const title = document.getElementById("modern-game-status");
  const detail = document.getElementById("modern-game-detail");
  if (!card || !title || !detail) return;

  const missing = !gameStatus.has_game;
  const running = Boolean(gameStatus.game_running);
  card.classList.toggle("is-missing", missing);
  card.classList.toggle("is-running", running);
  title.textContent = missing ? "Chưa tìm thấy game" : running ? "Game đang chạy" : "Sẵn sàng chơi";
  detail.textContent = missing
    ? "Chọn thư mục cài đặt để bắt đầu"
    : gameStatus.installed_vh
      ? `Việt hóa ${gameStatus.vh_version ? `v${gameStatus.vh_version}` : "đã cài đặt"} · ${launcherInfo.current === "heroic" ? "Heroic" : "Steam"}`
      : "Chưa cài Việt hóa · Có thể cập nhật ngay";
}

function updatePlayBtn() {
  const isRunning = Boolean(gameStatus.game_running);
  const text = isRunning ? "ĐANG CHƠI" : "CHƠI GAME";

  // Classic Play Button
  const btn = document.getElementById("btn-play");
  if (btn) {
    const textEl = btn.querySelector(".classic-play-text");
    if (textEl) {
      textEl.textContent = text;
    } else {
      btn.textContent = text;
    }
    btn.classList.toggle("running", isRunning);
  }

  // Modern Play Button
  const modernBtn = document.getElementById("btn-play-modern");
  if (modernBtn) {
    const textEl = modernBtn.querySelector(".play-text");
    if (textEl) {
      textEl.textContent = text;
    }
    modernBtn.classList.toggle("running", isRunning);
    modernBtn.disabled = isRunning;
  }

  // Cyber Play Button
  const cyberBtn = document.getElementById("btn-play-cyber");
  if (cyberBtn) {
    const titleEl = document.getElementById("cyber-play-title");
    if (titleEl) {
      titleEl.textContent = text;
    }
    cyberBtn.classList.toggle("running", isRunning);
    cyberBtn.disabled = isRunning;
  }
  const cyberStatus = document.getElementById("cyber-game-size-label");
  if (cyberStatus) cyberStatus.textContent = !gameStatus.has_game
    ? "Chưa tìm thấy game"
    : isRunning ? "Game đang chạy" : "Sẵn sàng";
  const cyberStatusBox = document.getElementById("cyber-status-text");
  if (cyberStatusBox) {
    cyberStatusBox.classList.toggle("is-missing", !gameStatus.has_game);
    cyberStatusBox.classList.toggle("is-running", isRunning);
  }
}

function updateLauncherBadge() {
  const curr = launcherInfo.current || "steam";
  const label = curr === "heroic" ? "Heroic" : "Steam";
  const badgeClass = `launcher-tag ${curr === "heroic" ? "heroic" : "steam"}`;

  const badgeClassic = document.getElementById("launcher-badge");
  const txtClassic = document.getElementById("launcher-badge-txt");
  if (badgeClassic) badgeClassic.className = badgeClass;
  if (txtClassic) txtClassic.textContent = label;

  const badgeModern = document.getElementById("launcher-badge-modern");
  const txtModern = document.getElementById("launcher-badge-txt-modern");
  if (badgeModern) badgeModern.className = badgeClass;
  if (txtModern) txtModern.textContent = label;

  const badgeCyber = document.getElementById("launcher-badge-cyber");
  const txtCyber = document.getElementById("launcher-badge-txt-cyber");
  if (badgeCyber) badgeCyber.className = `cyber-platform-badge ${curr === "heroic" ? "heroic" : "steam"}`;
  if (txtCyber) txtCyber.textContent = label;
}

// Poll game running status every 5s (optimized from 2.5s to reduce CPU overhead)
setInterval(refreshStatus, 5000);

// ── Background Video (Seamless Zero-Flicker Dual-Buffer Loop) & Audio ─────────

const vidA = document.getElementById("bg-video-a");
const vidB = document.getElementById("bg-video-b");
const audio = document.getElementById("bgm");
const volSlider = document.getElementById("volume-slider");
const volLabel = document.getElementById("vol-label");
const playBtn = document.getElementById("btn-play-music");
const dockMusicBtn = document.getElementById("dock-music-btn");
const dockMusicIcon = document.getElementById("dock-music-icon");

function updateMusicIcons(playing) {
  const playSvg = `<svg class="theme-svg-icon" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
  const pauseSvg = `<svg class="theme-svg-icon" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"></rect><rect x="14" y="4" width="4" height="16" rx="1"></rect></svg>`;
  if (playBtn) playBtn.innerHTML = playing ? pauseSvg : playSvg;
  if (dockMusicIcon) dockMusicIcon.innerHTML = playing ? pauseSvg : playSvg;
  const cyberPlayBtn = document.getElementById("cyber-btn-play-music");
  if (cyberPlayBtn) cyberPlayBtn.innerHTML = playing ? pauseSvg : playSvg;
  const drawerPlayBtn = document.getElementById("drawer-btn-play-music");
  if (drawerPlayBtn) drawerPlayBtn.innerHTML = playing ? pauseSvg : playSvg;
}

function initBgMedia() {
  const videoSrc = `${window.ASSETS_DIR}/bg-video-720p.mp4`;
  let currentVid = vidA;
  let nextVid = vidB;
  let isTransitioning = false;
  let isVideoPausedByFocusOrGame = false;
  let isMediaPausedByUser = false;

  function setupVideo(v) {
    if (!v) return;
    v.src = videoSrc;
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.onerror = () => {
      if (!v.dataset.fallbackTried) {
        v.dataset.fallbackTried = "1";
        v.src = "assets/bg-video-720p.mp4";
        v.load();
        v.play().catch(() => {});
      }
    };
    v.load();
  }

  setupVideo(vidA);
  setupVideo(vidB);

  if (vidA) {
    vidA.play().catch(() => {});
  }

  function handleTimeUpdate(v) {
    if (v !== currentVid || isTransitioning || isVideoPausedByFocusOrGame || isMediaPausedByUser) return;
    if (v.duration && v.currentTime >= v.duration - 0.5) {
      isTransitioning = true;
      if (nextVid) {
        nextVid.currentTime = 0;
        nextVid.play().then(() => {
          // Layer nextVid on TOP and fade in, while current stays beneath
          nextVid.classList.add("fade-in-top");
          setTimeout(() => {
            nextVid.classList.remove("fade-in-top");
            nextVid.classList.add("active");
            
            // Safely reset old video underneath
            currentVid.classList.remove("active", "fade-in-top");
            currentVid.pause();
            currentVid.currentTime = 0;
            
            // Swap pointers
            const temp = currentVid;
            currentVid = nextVid;
            nextVid = temp;
            isTransitioning = false;
          }, 420);
        }).catch(() => {
          isTransitioning = false;
        });
      } else {
        v.currentTime = 0;
        v.play().catch(() => {});
        isTransitioning = false;
      }
    }
  }

  if (vidA) {
    vidA.addEventListener("timeupdate", () => handleTimeUpdate(vidA));
    vidA.addEventListener("ended", () => {
      if (!isTransitioning && currentVid === vidA && !isVideoPausedByFocusOrGame && !isMediaPausedByUser) {
        vidA.currentTime = 0;
        vidA.play().catch(() => {});
      }
    });
  }

  if (vidB) {
    vidB.addEventListener("timeupdate", () => handleTimeUpdate(vidB));
    vidB.addEventListener("ended", () => {
      if (!isTransitioning && currentVid === vidB && !isVideoPausedByFocusOrGame && !isMediaPausedByUser) {
        vidB.currentTime = 0;
        vidB.play().catch(() => {});
      }
    });
  }

  // Setup Audio
  audio.src = `${window.ASSETS_DIR}/bgm.mp3`;
  audio.volume = 0.35;
  audio.loop = true;

  audio.onerror = () => {
    if (!audio.dataset.fallbackTried) {
      audio.dataset.fallbackTried = "1";
      audio.src = "assets/bgm.mp3";
      audio.load();
      tryPlay();
    }
  };

  // Auto-play audio immediately on launch
  const tryPlay = () => {
    audio.play().then(() => {
      updateMusicIcons(true);
    }).catch(() => {
      updateMusicIcons(false);
    });
  };

  audio.addEventListener("canplay", () => {
    if (audio.paused && !isMediaPausedByUser) {
      tryPlay();
    }
  }, { once: true });

  tryPlay();

  // Track if user has interacted with the launcher
  let hasUserInteracted = false;

  const markInteracted = () => {
    hasUserInteracted = true;
  };
  document.addEventListener("mousedown", markInteracted, { capture: true, passive: true });
  document.addEventListener("keydown", markInteracted, { capture: true, passive: true });

  // Media (Music & Background Video) toggle handler
  const toggleMusic = (e) => {
    if (e) e.stopPropagation();
    hasUserInteracted = true;

    const isAudioPlaying = audio && !audio.paused && !audio.ended;
    const isVideoPlaying = currentVid && !currentVid.paused && !currentVid.ended;
    const isPlaying = isAudioPlaying || isVideoPlaying;

    if (isPlaying) {
      isMediaPausedByUser = true;
      if (audio) audio.pause();
      if (currentVid) currentVid.pause();
      if (nextVid) nextVid.pause();
      updateMusicIcons(false);
    } else {
      isMediaPausedByUser = false;
      if (audio) audio.play().catch(() => { });
      if (currentVid) currentVid.play().catch(() => { });
      if (isTransitioning && nextVid) nextVid.play().catch(() => { });
      updateMusicIcons(true);
    }
  };

  if (playBtn) playBtn.onclick = toggleMusic;
  if (dockMusicBtn) dockMusicBtn.onclick = toggleMusic;
  const cyberPlayBtn = document.getElementById("cyber-btn-play-music");
  if (cyberPlayBtn) cyberPlayBtn.onclick = toggleMusic;
  const drawerPlayBtn = document.getElementById("drawer-btn-play-music");
  if (drawerPlayBtn) drawerPlayBtn.onclick = toggleMusic;

  if (audio) {
    audio.addEventListener("play", () => {
      if (!isMediaPausedByUser) updateMusicIcons(true);
    });
    audio.addEventListener("pause", () => {
      if (isMediaPausedByUser || (audio && audio.paused)) updateMusicIcons(false);
    });
  }

  let wasAudioPlayingBeforeGame = false;

  // Global pause/resume controller (chỉ dùng khi game thực sự đang chạy)
  window._pauseBgMedia = () => {
    isVideoPausedByFocusOrGame = true;
    if (currentVid) currentVid.pause();
    if (nextVid) nextVid.pause();
    if (audio && !audio.paused) {
      wasAudioPlayingBeforeGame = true;
      audio.pause();
    }
  };

  window._resumeBgMedia = () => {
    const isGameRunning = Boolean(gameStatus && gameStatus.game_running);
    if (!isGameRunning && !isMediaPausedByUser) {
      isVideoPausedByFocusOrGame = false;
      if (currentVid) currentVid.play().catch(() => {});
      if (wasAudioPlayingBeforeGame && audio && audio.paused) {
        wasAudioPlayingBeforeGame = false;
        audio.play().catch(() => {});
      }
    }
  };
}


// Volume slider with fill animation via CSS variable and localStorage persistence
function updateVolSlider(v, save = true) {
  if (volSlider) {
    const pct = `${v}%`;
    volSlider.style.setProperty("--vol-pct", pct);
    volSlider.value = v;
  }
  const cyberVol = document.getElementById("cyber-volume-slider");
  if (cyberVol) {
    cyberVol.style.setProperty("--vol-pct", `${v}%`);
    cyberVol.value = v;
  }
  const drawerVol = document.getElementById("drawer-volume-slider");
  if (drawerVol) {
    drawerVol.style.setProperty("--vol-pct", `${v}%`);
    drawerVol.value = v;
  }
  
  if (volLabel) volLabel.textContent = v;
  const drawerVolLabel = document.getElementById("drawer-vol-label");
  if (drawerVolLabel) drawerVolLabel.textContent = v;
  
  if (audio) audio.volume = v / 100;
  if (save) {
    try { localStorage.setItem("wuwavh_volume", String(v)); } catch { }
  }
}

if (volSlider) {
  volSlider.addEventListener("input", () => {
    updateVolSlider(parseInt(volSlider.value, 10), true);
  });
}

const cyberVol = document.getElementById("cyber-volume-slider");
if (cyberVol) {
  cyberVol.addEventListener("input", () => {
    updateVolSlider(parseInt(cyberVol.value, 10), true);
  });
}

const drawerVol = document.getElementById("drawer-volume-slider");
if (drawerVol) {
  drawerVol.addEventListener("input", () => {
    updateVolSlider(parseInt(drawerVol.value, 10), true);
  });
}

// ── Navigation & Tabs ──────────────────────────────────────────────────────

let currentTab = "home";
const tabHome = document.getElementById("tab-home");

const tabPerf = document.getElementById("tab-perf");
const tabFont = document.getElementById("tab-font");
const tabTheme = document.getElementById("tab-theme");

const dockTabHome = document.getElementById("dock-tab-home");

const dockTabPerf = document.getElementById("dock-tab-perf");
const dockTabFont = document.getElementById("dock-tab-font");
const dockTabTheme = document.getElementById("dock-tab-theme");

const drawerItemHome = document.getElementById("drawer-item-home");

const drawerItemPerf = document.getElementById("drawer-item-perf");
const drawerItemFont = document.getElementById("drawer-item-font");
const drawerItemTheme = document.getElementById("drawer-item-theme");

const sidebarDrawer = document.getElementById("sidebar-drawer");
const dockExpandBtn = document.getElementById("dock-expand-btn");
const drawerCollapseBtn = document.getElementById("drawer-collapse-btn");
const modernDrawerBackdrop = document.getElementById("modern-drawer-backdrop");

function setModernDrawerOpen(open) {
  if (!sidebarDrawer) return;
  sidebarDrawer.classList.toggle("open", open);
  sidebarDrawer.setAttribute("aria-hidden", String(!open));
  sidebarDrawer.inert = !open;
  if (modernDrawerBackdrop) modernDrawerBackdrop.classList.toggle("open", open);
  if (dockExpandBtn) dockExpandBtn.setAttribute("aria-expanded", String(open));
  if (open && drawerCollapseBtn) drawerCollapseBtn.focus();
  if (!open && sidebarDrawer.contains(document.activeElement) && dockExpandBtn) dockExpandBtn.focus();
}

const bottomLayer = document.getElementById("bottom-layer");

const perfPage = document.getElementById("perf-page");
const fontPage = document.getElementById("font-page");
const themePage = document.getElementById("theme-page");

function switchTab(tab) {
  currentTab = tab;

  // Close drawer if open
  setModernDrawerOpen(false);

  // Update Classic Nav tabs
  if (tabHome) tabHome.classList.toggle("active", tab === "home");

  if (tabPerf) tabPerf.classList.toggle("active", tab === "perf");
  if (tabFont) tabFont.classList.toggle("active", tab === "font");
  if (tabTheme) tabTheme.classList.toggle("active", tab === "theme");

  // Update Modern Dock tabs
  if (dockTabHome) dockTabHome.classList.toggle("active", tab === "home");

  if (dockTabPerf) dockTabPerf.classList.toggle("active", tab === "perf");
  if (dockTabFont) dockTabFont.classList.toggle("active", tab === "font");
  if (dockTabTheme) dockTabTheme.classList.toggle("active", tab === "theme");
  [[dockTabHome, "home"], [dockTabPerf, "perf"], [dockTabFont, "font"], [dockTabTheme, "theme"]]
    .forEach(([item, name]) => { if (item) item.setAttribute("aria-current", String(tab === name)); });

  // Update Modern Drawer items
  if (drawerItemHome) drawerItemHome.classList.toggle("active", tab === "home");

  if (drawerItemPerf) drawerItemPerf.classList.toggle("active", tab === "perf");
  if (drawerItemFont) drawerItemFont.classList.toggle("active", tab === "font");
  if (drawerItemTheme) drawerItemTheme.classList.toggle("active", tab === "theme");
  [[drawerItemHome, "home"], [drawerItemPerf, "perf"], [drawerItemFont, "font"], [drawerItemTheme, "theme"]]
    .forEach(([item, name]) => { if (item) item.setAttribute("aria-current", String(tab === name)); });

  // Update Cyber Nav tabs
  const cyberNavHome = document.getElementById("cyber-nav-home");
  const cyberNavPerf = document.getElementById("cyber-nav-perf");
  const cyberNavFont = document.getElementById("cyber-nav-font");
  const cyberNavTheme = document.getElementById("cyber-nav-theme");
  if (cyberNavHome) cyberNavHome.classList.toggle("active", tab === "home");
  if (cyberNavPerf) cyberNavPerf.classList.toggle("active", tab === "perf");
  if (cyberNavFont) cyberNavFont.classList.toggle("active", tab === "font");
  if (cyberNavTheme) cyberNavTheme.classList.toggle("active", tab === "theme");

  // Background blur trigger
  document.body.classList.toggle("tab-perf", tab === "perf");
  document.body.classList.toggle("tab-font", tab === "font");
  document.body.classList.toggle("tab-theme", tab === "theme");

  if (bottomLayer) bottomLayer.classList.toggle("hidden", tab !== "home");

  const cyberHome = document.getElementById("cyber-home");
  if (cyberHome) cyberHome.style.display = tab === "home" ? "" : "none";

  if (perfPage) perfPage.classList.toggle("visible", tab === "perf");
  if (fontPage) fontPage.classList.toggle("visible", tab === "font");
  if (themePage) themePage.classList.toggle("visible", tab === "theme");

  if (tab === "perf") {
    loadPerfSettings();
  } else if (tab === "font") {
    updateFontStatus();
  } else if (tab === "theme") {
    renderThemeList();
  }
}

// Attach Tab Clicks
if (tabHome) tabHome.onclick = () => switchTab("home");

if (tabPerf) tabPerf.onclick = () => switchTab("perf");
if (tabFont) tabFont.onclick = () => switchTab("font");
if (tabTheme) tabTheme.onclick = () => switchTab("theme");

if (dockTabHome) dockTabHome.onclick = () => switchTab("home");

if (dockTabPerf) dockTabPerf.onclick = () => switchTab("perf");
if (dockTabFont) dockTabFont.onclick = () => switchTab("font");
if (dockTabTheme) dockTabTheme.onclick = () => switchTab("theme");

if (drawerItemHome) drawerItemHome.onclick = () => switchTab("home");

if (drawerItemPerf) drawerItemPerf.onclick = () => switchTab("perf");
if (drawerItemFont) drawerItemFont.onclick = () => switchTab("font");
if (drawerItemTheme) drawerItemTheme.onclick = () => switchTab("theme");

// Cyber Sidebar Navigation
const cyberNavHome = document.getElementById("cyber-nav-home");
if (cyberNavHome) cyberNavHome.onclick = () => switchTab("home");
const cyberNavPerf = document.getElementById("cyber-nav-perf");
if (cyberNavPerf) cyberNavPerf.onclick = () => switchTab("perf");
const cyberNavFont = document.getElementById("cyber-nav-font");
if (cyberNavFont) cyberNavFont.onclick = () => switchTab("font");
const cyberNavTheme = document.getElementById("cyber-nav-theme");
if (cyberNavTheme) cyberNavTheme.onclick = () => switchTab("theme");
const cyberBtnGameFiles = document.getElementById("cyber-btn-game-files");
if (cyberBtnGameFiles) cyberBtnGameFiles.onclick = () => {
  if (!gameStatus.has_game) showPathModal();
  else ipc("open_game_folder").catch(e => toast(e.message, "error"));
};

// Drawer toggle buttons
if (dockExpandBtn) {
  dockExpandBtn.onclick = (e) => {
    e.stopPropagation();
    setModernDrawerOpen(true);
  };
}

if (drawerCollapseBtn) {
  drawerCollapseBtn.onclick = (e) => {
    e.stopPropagation();
    setModernDrawerOpen(false);
  };
}

document.addEventListener("click", (e) => {
  if (sidebarDrawer && sidebarDrawer.classList.contains("open")) {
    if (!sidebarDrawer.contains(e.target) && e.target !== dockExpandBtn) {
      setModernDrawerOpen(false);
    }
  }
});

if (modernDrawerBackdrop) modernDrawerBackdrop.onclick = () => setModernDrawerOpen(false);



// ── Context Menu (Dropdown) ────────────────────────────────────────────────

const menuToggleClassic = document.getElementById("btn-menu-toggle");
const menuToggleModern = document.getElementById("btn-menu-toggle-modern");
const ctxMenu = document.getElementById("ctx-menu");
let menuOpen = false;

function toggleMenu(open, triggerBtn) {
  menuOpen = (open !== undefined) ? open : !menuOpen;
  ctxMenu.classList.toggle("open", menuOpen);
  if (menuToggleClassic) menuToggleClassic.classList.toggle("active", menuOpen);
  if (menuToggleModern) menuToggleModern.classList.toggle("active", menuOpen);
  if (menuToggleModern) menuToggleModern.setAttribute("aria-expanded", String(menuOpen));
  const cyberMenuBtn = document.getElementById("btn-menu-toggle-cyber");
  if (cyberMenuBtn) cyberMenuBtn.classList.toggle("active", menuOpen);
  if (cyberMenuBtn) cyberMenuBtn.setAttribute("aria-expanded", String(menuOpen));

  if (menuOpen) {
    const btn = triggerBtn || (currentThemeId === "classic" ? menuToggleClassic : (currentThemeId === "cyber" ? cyberMenuBtn : menuToggleModern));
    if (btn) {
      const rect = btn.getBoundingClientRect();
      let left = rect.left;
      let bottom = window.innerHeight - rect.top + 8;

      // Prevent menu overflowing the right edge
      const menuWidth = 230;
      if (left + menuWidth > window.innerWidth) {
        left = window.innerWidth - menuWidth - 16;
      }

      ctxMenu.style.left = `${left}px`;
      ctxMenu.style.bottom = `${bottom}px`;
      ctxMenu.style.right = "auto";
      ctxMenu.style.top = "auto";
    }
  }
}

if (menuToggleClassic) {
  menuToggleClassic.onclick = (e) => {
    e.stopPropagation();
    toggleMenu(undefined, menuToggleClassic);
  };
}

if (menuToggleModern) {
  menuToggleModern.onclick = (e) => {
    e.stopPropagation();
    toggleMenu(undefined, menuToggleModern);
  };
}

const btnMenuToggleCyber = document.getElementById("btn-menu-toggle-cyber");
if (btnMenuToggleCyber) {
  btnMenuToggleCyber.onclick = (e) => {
    e.stopPropagation();
    toggleMenu(undefined, btnMenuToggleCyber);
  };
}

document.body.onclick = () => { if (menuOpen) toggleMenu(false); };
if (ctxMenu) ctxMenu.onclick = (e) => e.stopPropagation();

// ── Game Play Execution ────────────────────────────────────────────────────

async function handlePlayGame() {
  if (!gameStatus.has_game) {
    showPathModal();
    return;
  }
  try {
    toast("Đang khởi chạy game...", "success");
    await ipc("launch_game");
    await refreshStatus();
    setTimeout(refreshStatus, 2000);
    setTimeout(refreshStatus, 5000);
  } catch (e) {
    toast(`Lỗi chạy game: ${e.message}`, "error");
    await refreshStatus();
  }
}

const btnPlayClassic = document.getElementById("btn-play");
const btnPlayModern = document.getElementById("btn-play-modern");
const btnPlayCyber = document.getElementById("btn-play-cyber");
if (btnPlayClassic) btnPlayClassic.onclick = handlePlayGame;
if (btnPlayModern) btnPlayModern.onclick = handlePlayGame;
if (btnPlayCyber) btnPlayCyber.onclick = handlePlayGame;

const modernQuickUpdate = document.getElementById("modern-quick-update");
if (modernQuickUpdate) modernQuickUpdate.onclick = () => {
  if (!gameStatus.has_game) showPathModal();
  else startUpdate();
};

// ── Topbar Game files button ───────────────────────────────────────────────

const btnGameFiles = document.getElementById("btn-game-files");
if (btnGameFiles) {
  btnGameFiles.onclick = () => {
    if (!gameStatus.has_game) {
      showPathModal();
    } else {
      ipc("open_game_folder").catch(e => toast(e.message, "error"));
    }
  };
}



// ── Context Menu Actions ───────────────────────────────────────────────────

const launcherBadge = document.getElementById("launcher-badge");
if (launcherBadge) launcherBadge.onclick = () => openLauncherModal();

const launcherBadgeModern = document.getElementById("launcher-badge-modern");
if (launcherBadgeModern) launcherBadgeModern.onclick = () => openLauncherModal();

const launcherBadgeCyber = document.getElementById("launcher-badge-cyber");
if (launcherBadgeCyber) launcherBadgeCyber.onclick = () => openLauncherModal();

const ctxUpdate = document.getElementById("ctx-update");
if (ctxUpdate) {
  ctxUpdate.onclick = () => {
    toggleMenu(false);
    startUpdate();
  };
}

const ctxWineDll = document.getElementById("ctx-winedlloverrides");
if (ctxWineDll) {
  ctxWineDll.onclick = async () => {
    toggleMenu(false);
    try {
      const res = await ipc("install_wine_overrides");
      toast(res.message || "Đã cấu hình WINEDLLOVERRIDES thành công!", "success");
    } catch (e) {
      toast(`Lỗi: ${e.message}`, "error");
    }
  };
}

const ctxUpdateLauncher = document.getElementById("ctx-update-launcher");
if (ctxUpdateLauncher) {
  ctxUpdateLauncher.onclick = () => {
    toggleMenu(false);
    startUpdateAssets();
  };
}
const ctxCheckLauncherUpdate = document.getElementById("ctx-check-launcher-update");
if (ctxCheckLauncherUpdate) ctxCheckLauncherUpdate.onclick = () => {
  toggleMenu(false);
  startLauncherUpdate();
};

const ctxKill = document.getElementById("ctx-kill");
if (ctxKill) {
  ctxKill.onclick = async () => {
    toggleMenu(false);
    try {
      const res = await ipc("kill_game");
      if (res.killed) toast("Đã thoát game!", "success");
      else toast("Game không chạy.", "");
      await refreshStatus();
    } catch (e) {
      toast(`Lỗi: ${e.message}`, "error");
    }
  };
}

const ctxCredits = document.getElementById("ctx-credits");
if (ctxCredits) {
  ctxCredits.onclick = () => {
    toggleMenu(false);
    openCreditModal();
  };
}

const ctxUninstall = document.getElementById("ctx-uninstall");
if (ctxUninstall) {
  ctxUninstall.onclick = async () => {
    toggleMenu(false);
    if (!confirm("Bạn có chắc muốn gỡ bỏ hoàn toàn bản Việt Hoá?")) return;
    try {
      const res = await ipc("uninstall_mod");
      toast(`Đã gỡ bỏ ${res.removed.length} file.`, "success");
      await refreshStatus();
    } catch (e) {
      toast(`Lỗi: ${e.message}`, "error");
    }
  };
}

// ── High Performance Mode Controller ──────────────────────────────────────────

// ── High Performance & Graphics Settings (AlteriaX/WuWa-Configs) ──
const perfModeBadge = document.getElementById("perf-mode-badge");

// Mode Switch (Simple vs Advanced)
const btnModeSimple = document.getElementById("btn-mode-simple");
const btnModeAdvanced = document.getElementById("btn-mode-advanced");
const perfModeSubviewSimple = document.getElementById("perf-mode-subview-simple");
const perfModeSubviewAdvanced = document.getElementById("perf-mode-subview-advanced");

// Simple Mode Preset Details
const perfPresetDropdown = document.getElementById("perf-preset-dropdown");
const perfDetailTitle = document.getElementById("perf-detail-title");
const perfDetailSubtitle = document.getElementById("perf-detail-subtitle");
const perfDetailGpu = document.getElementById("perf-detail-gpu");
const perfApplyBtn = document.getElementById("perf-apply-btn");

// Advanced Mode Controls
const perfViewIniBtn = document.getElementById("perf-view-ini-btn");
const perfRestoreIniBtn = document.getElementById("perf-restore-ini-btn");
const perfSaveAdvancedBtn = document.getElementById("perf-save-advanced-btn");
const perfIniModal = document.getElementById("perf-ini-modal");
const perfIniCode = document.getElementById("perf-ini-code");
const perfIniCloseBtn = document.getElementById("perf-ini-close-btn");

// Anti-Lag & Engine Toggles
const perfToggleWp = document.getElementById("perf-toggle-wp");
const perfToggleUro = document.getElementById("perf-toggle-uro");
const perfToggleAsyncFx = document.getElementById("perf-toggle-async-fx");
const perfToggleEarlyZ = document.getElementById("perf-toggle-early-z");
const perfToggleShadowCsm = document.getElementById("perf-toggle-shadow-csm");
const perfToggleFoliageCull = document.getElementById("perf-toggle-foliage-cull");

// Core Graphics Toggles
const perfToggleShadow = document.getElementById("perf-toggle-shadow");
const perfToggleReflection = document.getElementById("perf-toggle-reflection");
const perfTogglePostprocess = document.getElementById("perf-toggle-postprocess");
const perfToggleGrass = document.getElementById("perf-toggle-grass");
const perfToggleKuro = document.getElementById("perf-toggle-kuro");
const perfToggleForceLod = document.getElementById("perf-toggle-force-lod");

// Sliders & Selects
const perfSliderScreenPct = document.getElementById("perf-slider-screen-pct");
const perfValScreenPct = document.getElementById("perf-val-screen-pct");
const perfSliderViewDist = document.getElementById("perf-slider-view-dist");
const perfValViewDist = document.getElementById("perf-val-view-dist");
const perfSliderStaticLod = document.getElementById("perf-slider-static-lod");
const perfValStaticLod = document.getElementById("perf-val-static-lod");
const perfSliderSkelLod = document.getElementById("perf-slider-skel-lod");
const perfValSkelLod = document.getElementById("perf-val-skel-lod");
const perfSliderNpcDist = document.getElementById("perf-slider-npc-dist");
const perfValNpcDist = document.getElementById("perf-val-npc-dist");
const perfSelectAniso = document.getElementById("perf-select-aniso");

const ALTERIAX_PRESETS = {
  "config-1": {
    name: "Cực cao",
    subtitle: "Chất lượng hình ảnh tối đa & chi tiết đồ họa cao nhất",
    gpu: "RTX 5090, 5080, 5070 Ti, 4090, 4080; RX 9070 XT, 7900 XTX"
  },
  "config-2": {
    name: "Cao",
    subtitle: "Đồ họa sắc nét, khử răng cưa và hiệu ứng đẹp",
    gpu: "RTX 5070, 5060 (Ti), 4070 (SUPER/Ti), 4060 Ti, 3090 (Ti), 3080 (Ti), 3070 (Ti), 2080 Ti; RX 9070, 9060 (XT), 7900 (XT/GRE), 7800 XT, 7700 XT, 6950 XT, 6900 XT, 6800 (XT)"
  },
  "config-3": {
    name: "Vừa lừa",
    subtitle: "Cân bằng hiệu năng và hình ảnh",
    gpu: "RTX 4060 / 4050 / 3060 / 3050; GTX 1660 SUPER/Ti / 1080 / 1070 Ti; RX 7600 / 6700 XT / 6600 / 5700 / 5600 XT; Arc B580 / B570 / A770 / A750 / A580"
  },
  "config-4": {
    name: "Tiết kiệm",
    subtitle: "Tối ưu cho GPU tầm trung & Laptop, chống sụt FPS",
    gpu: "RTX 3050 (Ti) Laptop, 2050, GTX 1660, 1650, 1070, 1060; RX 6500 XT, 6400, 5500 XT, 590, 580, 570, Radeon 890M; Arc 140V, A380, Arc iGPU"
  },
  "config-5": {
    name: "Siêu nhẹ",
    subtitle: "Tiết kiệm tài nguyên tối đa cho GPU onboard & máy yếu",
    gpu: "GTX 1650 (Ti) Laptop, 1050 (Ti), GT 1030, MX 450, 350, 250, 150; RX 560, 550, Radeon 780M, 680M, Vega iGPU; A310, Iris Xe, UHD Graphics"
  },
  "default": {
    name: "Mặc định (Khôi phục gốc)",
    subtitle: "Khôi phục lại toàn bộ file Engine.ini nguyên bản của game",
    gpu: "Tất cả các dòng card màn hình khi muốn khôi phục thiết lập gốc"
  }
};

let isPerfLoading = false;

function updatePresetDetailUI(presetId) {
  const p = ALTERIAX_PRESETS[presetId] || ALTERIAX_PRESETS["config-3"];
  if (perfDetailTitle) perfDetailTitle.textContent = p.name;
  if (perfDetailSubtitle) perfDetailSubtitle.textContent = p.subtitle;
  if (perfDetailGpu) perfDetailGpu.textContent = p.gpu;
  if (perfPresetDropdown && perfPresetDropdown.value !== presetId) {
    perfPresetDropdown.value = presetId;
  }
}

function switchPerfMode(mode) {
  const isSimple = (mode === "simple");
  if (btnModeSimple) btnModeSimple.classList.toggle("active", isSimple);
  if (btnModeAdvanced) btnModeAdvanced.classList.toggle("active", !isSimple);
  if (perfModeSubviewSimple) perfModeSubviewSimple.style.display = isSimple ? "block" : "none";
  if (perfModeSubviewAdvanced) perfModeSubviewAdvanced.style.display = !isSimple ? "block" : "none";
  if (perfModeBadge) perfModeBadge.textContent = isSimple ? "● Simple mode" : "● Advanced mode";
}

if (btnModeSimple) {
  btnModeSimple.addEventListener("click", () => switchPerfMode("simple"));
}
if (btnModeAdvanced) {
  btnModeAdvanced.addEventListener("click", () => switchPerfMode("advanced"));
}

if (perfPresetDropdown) {
  perfPresetDropdown.addEventListener("change", () => {
    updatePresetDetailUI(perfPresetDropdown.value);
  });
}

async function selectPerfPreset(presetName) {
  if (isPerfLoading) return;
  isPerfLoading = true;
  try {
    const updated = await ipc("apply_perf_preset", { preset: presetName });
    applySettingsToUI(updated);
    const pTitle = (ALTERIAX_PRESETS[presetName] || {}).name || presetName;
    toast(`✓ Đã áp dụng: ${pTitle}`, "success");
    if (perfIniModal && !perfIniModal.hidden) {
      loadEngineIniViewer();
    }
  } catch (e) {
    toast(`Lỗi áp dụng chế độ: ${e.message}`, "error");
  } finally {
    isPerfLoading = false;
  }
}

if (perfApplyBtn) {
  perfApplyBtn.addEventListener("click", () => {
    const selected = perfPresetDropdown ? perfPresetDropdown.value : "config-3";
    selectPerfPreset(selected);
  });
}

if (perfSaveAdvancedBtn) {
  perfSaveAdvancedBtn.addEventListener("click", () => {
    saveCurrentPerfSettings(true);
  });
}

async function loadEngineIniViewer() {
  if (!perfIniCode) return;
  try {
    const res = await ipc("get_engine_ini_text");
    perfIniCode.textContent = res.text || "File trống hoặc chưa có nội dung.";
  } catch (e) {
    perfIniCode.textContent = `Lỗi đọc Engine.ini: ${e.message}`;
  }
}

if (perfViewIniBtn) {
  perfViewIniBtn.addEventListener("click", () => {
    if (perfIniModal) {
      const isHidden = perfIniModal.hidden;
      perfIniModal.hidden = !isHidden;
      if (!perfIniModal.hidden) {
        loadEngineIniViewer();
      }
    }
  });
}

if (perfIniCloseBtn) {
  perfIniCloseBtn.addEventListener("click", () => {
    if (perfIniModal) perfIniModal.hidden = true;
  });
}

if (perfRestoreIniBtn) {
  perfRestoreIniBtn.addEventListener("click", async () => {
    try {
      await ipc("restore_perf_settings");
      toast("✓ Đã khôi phục Engine.ini gốc và đặt lại mặc định", "success");
      await loadPerfSettings();
    } catch (e) {
      toast(`Lỗi khôi phục: ${e.message}`, "error");
    }
  });
}


function applySettingsToUI(s) {
  if (!s || typeof s !== "object" || s.error) return;
  const activePreset = s.active_preset || (s.enabled ? "config-3" : "default");
  updatePresetDetailUI(activePreset);

  // Anti-Lag Toggles
  if (perfToggleWp) perfToggleWp.checked = Boolean(s.world_partition_opt);
  if (perfToggleUro) perfToggleUro.checked = Boolean(s.uro_opt);
  if (perfToggleAsyncFx) perfToggleAsyncFx.checked = Boolean(s.async_fx);
  if (perfToggleEarlyZ) perfToggleEarlyZ.checked = Boolean(s.early_z_pass);
  if (perfToggleShadowCsm) perfToggleShadowCsm.checked = Boolean(s.shadow_csm_opt);
  if (perfToggleFoliageCull) perfToggleFoliageCull.checked = Boolean(s.foliage_cull);

  // Graphics Toggles
  if (perfToggleShadow) perfToggleShadow.checked = Boolean(s.shadow_off);
  if (perfToggleReflection) perfToggleReflection.checked = Boolean(s.reflection_off);
  if (perfTogglePostprocess) perfTogglePostprocess.checked = Boolean(s.postprocess_off);
  if (perfToggleGrass) perfToggleGrass.checked = Boolean(s.grass_off);
  if (perfToggleKuro) perfToggleKuro.checked = Boolean(s.kuro_effects_off);
  if (perfToggleForceLod) perfToggleForceLod.checked = Boolean(s.force_component_lod);

  // Sliders
  if (perfSliderScreenPct) {
    perfSliderScreenPct.value = s.screen_percentage || 100;
    if (perfValScreenPct) perfValScreenPct.textContent = perfSliderScreenPct.value + "%";
  }
  if (perfSliderViewDist) {
    perfSliderViewDist.value = s.view_distance_scale !== undefined ? s.view_distance_scale : 1.0;
    if (perfValViewDist) perfValViewDist.textContent = perfSliderViewDist.value;
  }
  if (perfSliderStaticLod) {
    perfSliderStaticLod.value = s.static_mesh_lod_scale !== undefined ? s.static_mesh_lod_scale : 1.0;
    if (perfValStaticLod) perfValStaticLod.textContent = perfSliderStaticLod.value;
  }
  if (perfSliderSkelLod) {
    perfSliderSkelLod.value = s.skeletal_mesh_lod_bias !== undefined ? s.skeletal_mesh_lod_bias : 0;
    if (perfValSkelLod) perfValSkelLod.textContent = perfSliderSkelLod.value;
  }
  if (perfSliderNpcDist) {
    perfSliderNpcDist.value = s.npc_disappear_dist || 2000;
    if (perfValNpcDist) perfValNpcDist.textContent = perfSliderNpcDist.value;
  }
  if (perfSelectAniso) {
    perfSelectAniso.value = String(s.max_anisotropy || 16);
  }
}

async function loadPerfSettings() {
  isPerfLoading = true;
  try {
    const s = await ipc("get_perf_settings");
    applySettingsToUI(s);
  } catch (e) {
    console.error("[Perf Load Error]", e);
  } finally {
    isPerfLoading = false;
  }
}

async function saveCurrentPerfSettings(showToast = true) {
  if (isPerfLoading) return;

  const settings = {
    enabled: true,
    active_preset: "custom",
    // Anti-Lag Toggles
    world_partition_opt: perfToggleWp ? perfToggleWp.checked : true,
    uro_opt: perfToggleUro ? perfToggleUro.checked : true,
    async_fx: perfToggleAsyncFx ? perfToggleAsyncFx.checked : true,
    early_z_pass: perfToggleEarlyZ ? perfToggleEarlyZ.checked : true,
    shadow_csm_opt: perfToggleShadowCsm ? perfToggleShadowCsm.checked : false,
    foliage_cull: perfToggleFoliageCull ? perfToggleFoliageCull.checked : false,
    // Graphics Toggles
    shadow_off: perfToggleShadow ? perfToggleShadow.checked : false,
    reflection_off: perfToggleReflection ? perfToggleReflection.checked : false,
    postprocess_off: perfTogglePostprocess ? perfTogglePostprocess.checked : false,
    grass_off: perfToggleGrass ? perfToggleGrass.checked : false,
    kuro_effects_off: perfToggleKuro ? perfToggleKuro.checked : false,
    force_component_lod: perfToggleForceLod ? perfToggleForceLod.checked : false,
    // Sliders
    screen_percentage: perfSliderScreenPct ? parseInt(perfSliderScreenPct.value, 10) : 100,
    view_distance_scale: perfSliderViewDist ? parseFloat(perfSliderViewDist.value) : 1.0,
    static_mesh_lod_scale: perfSliderStaticLod ? parseFloat(perfSliderStaticLod.value) : 1.0,
    skeletal_mesh_lod_bias: perfSliderSkelLod ? parseInt(perfSliderSkelLod.value, 10) : 0,
    npc_disappear_dist: perfSliderNpcDist ? parseInt(perfSliderNpcDist.value, 10) : 2000,
    max_anisotropy: perfSelectAniso ? parseInt(perfSelectAniso.value, 10) : 16,
  };

  try {
    const updated = await ipc("save_perf_settings", { settings });
    applySettingsToUI(updated);
    if (showToast) {
      toast("✓ Đã lưu cấu hình Advanced thành công", "success");
    }
  } catch (e) {
    toast(`Lỗi lưu hiệu năng: ${e.message}`, "error");
  }
}

// Attach Slider Input Events (Realtime Label Update)
const bindSlider = (slider, labelEl, suffix = "") => {
  if (!slider) return;
  slider.addEventListener("input", () => {
    if (labelEl) labelEl.textContent = slider.value + suffix;
  });
};

bindSlider(perfSliderScreenPct, perfValScreenPct, "%");
bindSlider(perfSliderViewDist, perfValViewDist);
bindSlider(perfSliderStaticLod, perfValStaticLod);
bindSlider(perfSliderSkelLod, perfValSkelLod);
bindSlider(perfSliderNpcDist, perfValNpcDist);

// ── Font Customizer (Supporting Both Classic and Modern Views) ──────────────

const fontCurrent = document.getElementById("font-current");
const fontDetail = document.getElementById("font-detail");
const fontStatusIcon = document.getElementById("font-status-icon");
const fontPickCustomBtn = document.getElementById("font-pick-custom");
const fontPickPakBtn = document.getElementById("font-pick-pak");
const fontInstallDefaultBtn = document.getElementById("font-install-default");

const modernFontCurrentVal = document.getElementById("modern-font-current-val");
const modernFontRestoreBtn = document.getElementById("modern-btn-restore-default");
const modernFontPathInput = document.getElementById("modern-font-path");
const modernFontBrowseBtn = document.getElementById("modern-btn-browse");
const modernFontInstallBtn = document.getElementById("modern-btn-install");
const modernFontPickPakBtn = document.getElementById("modern-btn-pick-pak");
const fontProgress = document.getElementById("font-progress");
const fontProgressText = document.getElementById("font-progress-text");

let selectedFontFilePath = "";
let fontPreviewFace = null;
let fontPreviewRequest = 0;

function clearFontPreview() {
  for (const el of [fontCurrent, modernFontCurrentVal]) {
    if (el) el.style.removeProperty("font-family");
  }
  if (fontPreviewFace && document.fonts) document.fonts.delete(fontPreviewFace);
  fontPreviewFace = null;
}

async function applyFontPreview(preview, requestId) {
  if (requestId !== fontPreviewRequest || !preview?.data ||
      !["font/ttf", "font/otf"].includes(preview.mime) ||
      !window.FontFace || !document.fonts) return;
  const family = `WuWaVHFontPreview${requestId}`;
  const face = new FontFace(family, `url(data:${preview.mime};base64,${preview.data})`);
  await face.load();
  if (requestId !== fontPreviewRequest) return;
  document.fonts.add(face);
  fontPreviewFace = face;
  for (const el of [fontCurrent, modernFontCurrentVal]) {
    if (el) el.style.setProperty("font-family", `"${family}", "Noto Sans", sans-serif`, "important");
  }
}

async function updateFontStatus() {
  const requestId = ++fontPreviewRequest;
  clearFontPreview();
  if (modernFontCurrentVal) modernFontCurrentVal.textContent = "Đang kiểm tra...";
  if (fontCurrent) fontCurrent.textContent = "Đang kiểm tra...";

  try {
    const status = await ipc("get_font_status");
    if (requestId !== fontPreviewRequest) return;
    let display = "Chưa cài font";
    let detail = "Hãy cài font để hiển thị tiếng Việt đúng";
    let icon = "⚠️";

    if (status.active_font === "custom") {
      display = status.custom_font_name || "Font tuỳ chỉnh";
      detail = "Font tuỳ chỉnh đang được sử dụng";
      icon = "🎨";
    } else if (status.active_font === "default") {
      display = "LaguSans Bold (Mặc định)";
      detail = "Font mặc định của bản Việt Hoá";
      icon = "✅";
    }

    // Update Modern View
    if (modernFontCurrentVal) {
      modernFontCurrentVal.textContent = display;
      modernFontCurrentVal.title = display;
    }
    if (modernFontRestoreBtn) {
      modernFontRestoreBtn.disabled = !status.default_available;
    }

    // Update Classic View
    if (fontCurrent) {
      fontCurrent.textContent = status.active_font === "custom" ? (status.custom_font_name || "Custom Font") : (status.active_font === "default" ? "LaguSans Bold" : "Chưa cài font");
      fontCurrent.className = `font-status-value ${status.active_font}`;
    }
    if (fontDetail) fontDetail.textContent = detail;
    if (fontStatusIcon) fontStatusIcon.textContent = icon;
    if (fontInstallDefaultBtn) {
      fontInstallDefaultBtn.disabled = !status.default_available;
    }
    if (status.active_font !== "none") {
      try {
        const preview = await ipc("get_font_preview");
        await applyFontPreview(preview, requestId);
      } catch (e) {
        console.warn("[Font Preview Error]", e);
      }
    }
  } catch (e) {
    if (requestId !== fontPreviewRequest) return;
    if (modernFontCurrentVal) modernFontCurrentVal.textContent = `Lỗi: ${e.message}`;
    if (fontCurrent) fontCurrent.textContent = `Lỗi: ${e.message}`;
  }
}

// ── Modern Font Actions ──

// 1. Browse Font File (TTF, OTF, PAK)
if (modernFontBrowseBtn) {
  modernFontBrowseBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    try {
      const pick = await ipc("pick_font_file");
      if (!pick.path) return; // User cancelled

      selectedFontFilePath = pick.path;
      if (modernFontPathInput) {
        modernFontPathInput.value = pick.path.split("/").pop();
      }
    } catch (e) {
      toast(`Lỗi mở file: ${e.message}`, "error");
    }
  };
}

// 2. Install Custom Font Button (TTF / OTF / PAK)
if (modernFontInstallBtn) {
  modernFontInstallBtn.onclick = async () => {
    if (!selectedFontFilePath) {
      toast("Vui lòng duyệt và chọn file font trước!", "error");
      return;
    }

    const isPak = selectedFontFilePath.toLowerCase().endsWith(".pak");
    if (fontProgress) fontProgress.style.display = "block";
    if (fontProgressText) fontProgressText.textContent = isPak ? "📦 Đang cài đặt font từ file PAK..." : "⚙️ Đang chuyển đổi và cài đặt font...";

    try {
      const result = await ipc("install_font", {
        path: selectedFontFilePath
      });

      if (fontProgress) fontProgress.style.display = "none";
      toast(`✓ Đã cài đặt font: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi cài font: ${e.message}`, "error");
    }
  };
}

// 2b. Direct Install from PAK Button (Modern)
if (modernFontPickPakBtn) {
  modernFontPickPakBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    try {
      const pick = await ipc("pick_font_pak");
      if (!pick.path) return;

      selectedFontFilePath = pick.path;
      if (modernFontPathInput) {
        modernFontPathInput.value = pick.path.split("/").pop();
      }

      if (fontProgress) fontProgress.style.display = "block";
      if (fontProgressText) fontProgressText.textContent = "📦 Đang cài đặt font từ file PAK...";

      const result = await ipc("install_font_from_pak", { path: pick.path });
      if (fontProgress) fontProgress.style.display = "none";
      toast(`✓ Đã cài font PAK: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi cài font PAK: ${e.message}`, "error");
    }
  };
}

// 3. Restore Default Font Button (Modern)
if (modernFontRestoreBtn) {
  modernFontRestoreBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    if (fontProgress) fontProgress.style.display = "block";
    if (fontProgressText) fontProgressText.textContent = "↩️ Đang khôi phục font gốc LaguSans Bold...";

    try {
      const result = await ipc("install_default_font");
      if (fontProgress) fontProgress.style.display = "none";
      toast(`✓ Đã khôi phục font gốc: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi: ${e.message}`, "error");
    }
  };
}

// ── Classic Font Actions ──

if (fontPickCustomBtn) {
  fontPickCustomBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    if (fontProgress) fontProgress.style.display = "block";
    if (fontProgressText) fontProgressText.textContent = "📂 Đang mở hộp thoại chọn file...";

    try {
      const pick = await ipc("pick_font_file");
      if (!pick.path) {
        if (fontProgress) fontProgress.style.display = "none";
        return;
      }

      const isPak = pick.path.toLowerCase().endsWith(".pak");
      if (fontProgressText) fontProgressText.textContent = isPak ? "📦 Đang cài đặt font từ file PAK..." : "⚙️ Đang chuyển đổi và cài đặt font...";
      const result = isPak ? await ipc("install_font_from_pak", { path: pick.path }) : await ipc("install_font", { path: pick.path });
      if (fontProgress) fontProgress.style.display = "none";

      toast(`✓ Đã cài font: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi cài font: ${e.message}`, "error");
    }
  };
}

if (fontPickPakBtn) {
  fontPickPakBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    if (fontProgress) fontProgress.style.display = "block";
    if (fontProgressText) fontProgressText.textContent = "📂 Đang mở hộp thoại chọn file PAK...";

    try {
      const pick = await ipc("pick_font_pak");
      if (!pick.path) {
        if (fontProgress) fontProgress.style.display = "none";
        return;
      }

      if (fontProgressText) fontProgressText.textContent = "📦 Đang cài đặt font từ file PAK...";
      const result = await ipc("install_font_from_pak", { path: pick.path });
      if (fontProgress) fontProgress.style.display = "none";

      toast(`✓ Đã cài font PAK: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi cài font PAK: ${e.message}`, "error");
    }
  };
}

if (fontInstallDefaultBtn) {
  fontInstallDefaultBtn.onclick = async () => {
    if (!gameStatus.has_game) {
      toast("Hãy chọn thư mục game trước!", "error");
      showPathModal();
      return;
    }

    if (fontProgress) fontProgress.style.display = "block";
    if (fontProgressText) fontProgressText.textContent = "↩️ Đang cài font mặc định...";

    try {
      const result = await ipc("install_default_font");
      if (fontProgress) fontProgress.style.display = "none";

      toast(`✓ Đã cài font: ${result.font_name}`, "success");
      updateFontStatus();
      await refreshStatus();
    } catch (e) {
      if (fontProgress) fontProgress.style.display = "none";
      toast(`Lỗi: ${e.message}`, "error");
    }
  };
}

// ── Theme Switcher System (Modular External Themes) ────────────────────────

let currentThemeId = "classic";

function applyTheme(themeId, save = true) {
  if (themeId === "oriental") themeId = "cyber";
  const themeListDefs = (typeof THEMES !== "undefined") ? THEMES : [];
  const themeObj = themeListDefs.find(t => t.id === themeId) || themeListDefs[0];
  const activeId = themeObj ? themeObj.id : themeId;

  currentThemeId = activeId;
  const usesModernLayout = activeId === "modern" || activeId === "cyber";

  // 1. Swap theme stylesheet dynamically from themes/ directory
  const linkEl = document.getElementById("theme-stylesheet");
  if (linkEl && themeObj && themeObj.css) {
    linkEl.setAttribute("href", themeObj.css);
  }

  // 2. Update body classes & attributes
  document.body.classList.remove("theme-modern", "theme-classic", "theme-oriental", "theme-cyber");
  document.body.classList.add(`theme-${activeId}`);
  document.body.classList.toggle("theme-modern-layout", usesModernLayout);
  document.body.classList.toggle("theme-classic-layout", !usesModernLayout);
  document.body.setAttribute("data-theme", activeId);

  // 3. Update active state on visible theme cards
  document.querySelectorAll(".theme-card").forEach(card => {
    card.classList.toggle("active", card.dataset.themeId === activeId);
  });

  if (save) {
    try { localStorage.setItem("wuwavh_theme", activeId); } catch { }
    ipc("set_theme", { theme: activeId }).catch(() => { });
    const tName = themeObj ? themeObj.name : activeId;
    toast(`🎨 Đã áp dụng giao diện: ${tName}`, "success");
  }
}

function renderThemeList() {
  const themeList = document.getElementById("theme-list");
  if (!themeList) return;
  const themeListDefs = (typeof THEMES !== "undefined") ? THEMES : [];
  themeList.innerHTML = "";

  themeListDefs.forEach(t => {
    const card = document.createElement("div");
    const isActive = t.id === currentThemeId;
    card.className = `theme-card ${t.id}-theme-card${isActive ? " active" : ""}`;
    card.dataset.themeId = t.id;
    const accent = t.accentColor || "#f0d89a";

    const iconHtml = t.iconSvg || `<svg class="theme-card-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>`;
    const tag = t.tag || "Giao diện";
    const sub = t.subtitle || "";
    const desc = t.description || "";
    const paletteDots = (t.palette || [accent, "#334155"]).map(c => `<span class="theme-dot" style="background:${c}"></span>`).join("");

    card.innerHTML = `
      <div class="theme-card-banner" style="background:${t.previewGradient}">
        <div class="theme-banner-overlay"></div>
        <div class="theme-banner-mockup ${t.id}-mockup">
          <div class="mockup-header-bar"></div>
          <div class="mockup-body-area">
            <div class="mockup-elem-a"></div>
            <div class="mockup-elem-b"></div>
          </div>
        </div>
        <span class="theme-card-tag">${tag}</span>
        ${isActive ? '<span class="theme-badge-active"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> ĐANG DÙNG</span>' : ''}
      </div>

      <div class="theme-card-body">
        <div class="theme-card-top-row">
          <div class="theme-icon-box" style="color: ${accent}; border-color: ${accent}40; background: ${accent}15;">
            ${iconHtml}
          </div>
          <div class="theme-card-titles">
            <div class="theme-card-name">${t.name}</div>
            <div class="theme-card-sub">${sub}</div>
          </div>
        </div>

        <div class="theme-card-footer">
          <div class="theme-palette-wrap" title="Tông màu chủ đạo">
            ${paletteDots}
          </div>
          <button class="theme-apply-btn ${isActive ? 'applied' : ''}">
            ${isActive ? 'Đã kích hoạt' : 'Áp dụng'}
          </button>
        </div>
      </div>
    `;

    card.onclick = () => {
      applyTheme(t.id, true);
      renderThemeList();
    };

    themeList.appendChild(card);
  });
}

// ── Update Progress System (Inline Bottom Progress Bar) ─────────────────────

let updateProgressHideTimer = null;

function showUpdateProgress(pct, statusText, isError = false) {
  if (updateProgressHideTimer) {
    clearTimeout(updateProgressHideTimer);
    updateProgressHideTimer = null;
  }
  const configs = [
    { box: "cyber-launch-progress", bar: "cyber-progress-bar", pct: "cyber-progress-pct", status: "cyber-progress-status" },
    { box: "classic-launch-progress", bar: "classic-progress-bar", pct: "classic-progress-pct", status: "classic-progress-status" },
    { box: "modern-launch-progress", bar: "modern-progress-bar", pct: "modern-progress-pct", status: "modern-progress-status" }
  ];

  configs.forEach(({ box, bar, pct: pctId, status }) => {
    const boxEl = document.getElementById(box);
    const barEl = document.getElementById(bar);
    const pctEl = document.getElementById(pctId);
    const statusEl = document.getElementById(status);

    if (boxEl) boxEl.style.display = "flex";
    if (barEl) {
      barEl.style.width = `${pct}%`;
      if (isError) {
        barEl.style.background = "#ef4444";
        barEl.style.boxShadow = "0 0 10px rgba(239, 68, 68, 0.8)";
      } else {
        barEl.style.background = "";
        barEl.style.boxShadow = "";
      }
    }
    if (pctEl) {
      pctEl.textContent = `${pct}%`;
      if (isError) pctEl.style.color = "#ef4444";
      else pctEl.style.color = "";
    }
    if (statusEl && statusText) {
      statusEl.textContent = statusText;
      if (isError) statusEl.style.color = "#ef4444";
      else statusEl.style.color = "";
    }
  });
}

function hideUpdateProgress(delay = 0) {
  const boxIds = ["cyber-launch-progress", "classic-launch-progress", "modern-launch-progress"];
  if (updateProgressHideTimer) clearTimeout(updateProgressHideTimer);
  updateProgressHideTimer = setTimeout(() => {
    boxIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = "none";
    });
    updateProgressHideTimer = null;
  }, delay);
}

function onUpdateProgress(d) {
  const pct = Math.round((d.progress || 0) * 100);
  const label = d.label || d.file || "Bản dịch";
  let statusText = `[${(d.step || 0) + 1}/${d.total || 3}] ${label}`;
  if (d.mb_total) {
    statusText += ` (${d.mb_done || 0} / ${d.mb_total} MB)`;
  }
  if (d.speed) {
    statusText += ` · ${d.speed}`;
  }
  showUpdateProgress(pct, statusText);
}

async function onUpdateDone(d) {
  modUpdateInProgress = false;
  if (modernQuickUpdate) modernQuickUpdate.disabled = false;
  showUpdateProgress(100, "✓ CẬP NHẬT VIỆT HOÁ HOÀN TẤT!");
  toast("✓ Đã cập nhật bản dịch Việt Hoá mới nhất!", "success");
  await Promise.allSettled([refreshStatus(), loadVersion()]);
  hideUpdateProgress(2500);
}

function onUpdateError(d) {
  modUpdateInProgress = false;
  if (modernQuickUpdate) modernQuickUpdate.disabled = false;
  const errMsg = (d && d.error) || "Lỗi không xác định";
  showUpdateProgress(0, `❌ Lỗi: ${errMsg}`, true);
  toast(`Lỗi cập nhật: ${errMsg}`, "error");
  hideUpdateProgress(4000);
}

function onUpdateAssetsProgress(d) {
  const pct = Math.round((d.progress || 0) * 100);
  const label = d.label || d.file || "Media";
  let statusText = `[${(d.step || 0) + 1}/${d.total || 2}] ${label}`;
  if (d.mb_total) {
    statusText += ` (${d.mb_done || 0} / ${d.mb_total} MB)`;
  }
  if (d.speed) {
    statusText += ` · ${d.speed}`;
  }
  showUpdateProgress(pct, statusText);
}

function onUpdateAssetsDone() {
  mediaUpdateInProgress = false;
  showUpdateProgress(100, "✓ CẬP NHẬT MEDIA LAUNCHER HOÀN TẤT!");
  toast("✓ Đã tải video và nhạc nền mới nhất!", "success");
  if (typeof initBgMedia === "function") initBgMedia();
  hideUpdateProgress(2500);
}

function onUpdateAssetsError(d) {
  mediaUpdateInProgress = false;
  const errMsg = (d && d.error) || "Lỗi không xác định";
  showUpdateProgress(0, `❌ Lỗi: ${errMsg}`, true);
  toast(`Lỗi tải Media: ${errMsg}`, "error");
  hideUpdateProgress(4000);
}

let modUpdateInProgress = false;
let mediaUpdateInProgress = false;

function startUpdate() {
  if (modUpdateInProgress) return;
  if (launcherUpdateBusy || mediaUpdateInProgress) {
    toast("Hãy chờ lượt cập nhật hiện tại hoàn tất.", "info");
    return;
  }
  modUpdateInProgress = true;
  if (modernQuickUpdate) modernQuickUpdate.disabled = true;
  switchTab("home");
  showUpdateProgress(0, "Đang kết nối máy chủ cập nhật...");
  toast("Đang tải cập nhật Việt Hoá...", "info");
  ipc("update_mod").catch((e) => onUpdateError({ error: e.message }));
}

function startUpdateAssets() {
  if (mediaUpdateInProgress) return;
  if (launcherUpdateBusy || modUpdateInProgress) {
    toast("Hãy chờ lượt cập nhật hiện tại hoàn tất.", "info");
    return;
  }
  mediaUpdateInProgress = true;
  switchTab("home");
  showUpdateProgress(0, "Đang kết nối máy chủ Media...");
  toast("Đang tải Media Launcher mới...", "info");
  ipc("update_assets").catch((e) => onUpdateAssetsError({ error: e.message }));
}

// ── Game Path Modal ────────────────────────────────────────────────────────

const pathModal = document.getElementById("path-modal");

function showPathModal() {
  pathModal.classList.add("visible");
  document.getElementById("path-status").textContent = "";
  document.getElementById("path-input").focus();
}

async function submitPath() {
  const input = document.getElementById("path-input");
  const status = document.getElementById("path-status");
  const path = input.value.trim();
  if (!path) return;
  status.textContent = "Đang kiểm tra...";
  try {
    await ipc("set_game_path", { path });
    pathModal.classList.remove("visible");
    toast("Đã lưu thư mục game!", "success");
    await refreshStatus();
  } catch (e) {
    status.style.color = "#ef4444";
    status.textContent = `❌ ${e.message}`;
  }
}

// ── Launcher Selection Modal ───────────────────────────────────────────────

const launcherModal = document.getElementById("launcher-modal");
const optSteam = document.getElementById("opt-steam");
const optHeroic = document.getElementById("opt-heroic");
const steamBadge = document.getElementById("steam-badge");
const heroicBadge = document.getElementById("heroic-badge");
const steamDetail = document.getElementById("steam-status-detail");
const heroicDetail = document.getElementById("heroic-status-detail");

function openLauncherModal() {
  launcherModal.classList.add("visible");
  updateLauncherModalUI();
}

function closeLauncherModal() {
  launcherModal.classList.remove("visible");
}

// ── Credit / About Modal ───────────────────────────────────────────────────
const creditModal = document.getElementById("credit-modal");

function openCreditModal() {
  if (creditModal) creditModal.classList.add("visible");
}

function closeCreditModal() {
  if (creditModal) creditModal.classList.remove("visible");
}

function openDiscordLink() {
  const url = "https://discord.gg/uNRyaHJR6";
  ipc("open_url", { url }).catch(() => {
    window.open(url, "_blank");
  });
}

if (creditModal) {
  creditModal.onclick = (e) => {
    if (e.target === creditModal) closeCreditModal();
  };
}

function updateLauncherModalUI() {
  const curr = launcherInfo.current || "steam";
  const heroicAvail = launcherInfo.heroic_available || (launcherInfo.heroic && launcherInfo.heroic.available);
  const heroicHasGame = launcherInfo.heroic_has_game || (launcherInfo.heroic && launcherInfo.heroic.game_found);
  const heroicGame = launcherInfo.heroic_game || (launcherInfo.heroic && launcherInfo.heroic.game_title ? launcherInfo.heroic : null);
  const steamAvail = launcherInfo.steam_available || (launcherInfo.steam && launcherInfo.steam.available);

  if (optSteam) optSteam.classList.toggle("selected", curr === "steam");
  if (optHeroic) optHeroic.classList.toggle("selected", curr === "heroic");

  // Steam status
  if (steamBadge && steamDetail) {
    if (steamAvail) {
      steamBadge.textContent = "Khả dụng ✓";
      steamBadge.className = "launcher-opt-badge ok";
      steamDetail.textContent = "Đã phát hiện Steam trên hệ thống";
    } else {
      steamBadge.textContent = "Chưa cài đặt";
      steamBadge.className = "launcher-opt-badge";
      steamDetail.textContent = "Không tìm thấy Steam trên hệ thống";
    }
  }

  // Heroic status
  if (heroicBadge && heroicDetail) {
    if (heroicAvail && heroicHasGame) {
      heroicBadge.textContent = "Đã nhận diện ✓";
      heroicBadge.className = "launcher-opt-badge ok";
      const title = (heroicGame && (heroicGame.title || heroicGame.game_title)) || 'Wuthering Waves';
      const runner = (heroicGame && heroicGame.runner) || 'sideload';
      heroicDetail.textContent = `Tìm thấy game: ${title} (Runner: ${runner})`;
    } else if (heroicAvail) {
      heroicBadge.textContent = "Đã cài đặt ✓";
      heroicBadge.className = "launcher-opt-badge ok";
      heroicDetail.textContent = "Đã phát hiện Heroic Games Launcher trên hệ thống";
    } else {
      heroicBadge.textContent = "Chưa cài đặt";
      heroicBadge.className = "launcher-opt-badge";
      heroicDetail.textContent = "Không tìm thấy Heroic Games Launcher trên hệ thống";
    }
  }
}

async function selectLauncher(type) {
  try {
    await ipc("set_launcher", { launcher: type });
    launcherInfo.current = type;
    try { localStorage.setItem("wuwavh_launcher", type); } catch { }
    updateLauncherBadge();
    updateModernStatus();
    updateLauncherModalUI();
    toast(`Đã đổi launcher chạy game thành: ${type === "heroic" ? "Heroic Games Launcher" : "Steam"}`, "success");
    setTimeout(closeLauncherModal, 400);
  } catch (e) {
    toast(`Lỗi: ${e.message}`, "error");
  }
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (menuOpen) toggleMenu(false);
    else if (sidebarDrawer && sidebarDrawer.classList.contains("open"))
      setModernDrawerOpen(false);
    else if (launcherModal && launcherModal.classList.contains("visible"))
      closeLauncherModal();
    else if (pathModal && pathModal.classList.contains("visible"))
      pathModal.classList.remove("visible");
    else if (creditModal && creditModal.classList.contains("visible"))
      closeCreditModal();
    else if (perfIniModal && !perfIniModal.hidden)
      perfIniModal.hidden = true;
    else if (currentTab !== "home")
      switchTab("home");
  }
});

// ── Initializer ────────────────────────────────────────────────────────────

async function init() {
  // Load saved theme
  let savedTheme = "classic";
  try {
    savedTheme = localStorage.getItem("wuwavh_theme") || "classic";
    if (savedTheme === "oriental") savedTheme = "cyber";
  } catch { }
  applyTheme(savedTheme, false);

  // Load saved launcher preference
  try {
    const savedLauncher = localStorage.getItem("wuwavh_launcher");
    if (savedLauncher) {
      launcherInfo.current = savedLauncher;
      updateLauncherBadge();
    }
  } catch { }

  // Launch options listeners
  const dx11M = document.getElementById("toggle-dx11-modern");
  if (dx11M) dx11M.onclick = toggleDx11;
  if (dx11M) dx11M.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleDx11(e); } };
  const dx11C = document.getElementById("toggle-dx11-classic");
  if (dx11C) dx11C.onclick = toggleDx11;
  const dx11Cy = document.getElementById("toggle-dx11-cyber");
  if (dx11Cy) dx11Cy.onclick = toggleDx11;
  if (dx11Cy) dx11Cy.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleDx11(e); } };

  const csharpM = document.getElementById("toggle-csharp-modern");
  if (csharpM) csharpM.onclick = toggleCSharpEnv;
  if (csharpM) csharpM.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleCSharpEnv(e); } };
  const csharpC = document.getElementById("toggle-csharp-classic");
  if (csharpC) csharpC.onclick = toggleCSharpEnv;
  const csharpCy = document.getElementById("toggle-csharp-cyber");
  if (csharpCy) csharpCy.onclick = toggleCSharpEnv;
  if (csharpCy) csharpCy.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleCSharpEnv(e); } };

  const badgeCy = document.getElementById("launcher-badge-cyber");
  if (badgeCy) badgeCy.onclick = () => openLauncherModal();
  if (badgeCy) badgeCy.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openLauncherModal(); } };

  // Restore saved volume
  let savedVol = 35;
  try {
    const v = localStorage.getItem("wuwavh_volume");
    if (v !== null && !isNaN(parseInt(v, 10))) {
      savedVol = Math.max(0, Math.min(100, parseInt(v, 10)));
    }
  } catch { }
  updateVolSlider(savedVol, false);

  initBgMedia();
  if (typeof window !== "undefined" && window.LAUNCHER_VERSION) {
    updateLauncherVersionUI(window.LAUNCHER_VERSION);
  }
  await Promise.allSettled([loadVersion(), refreshStatus()]);
  checkLauncherUpdate(true).catch(() => { });

  if (gameStatus && gameStatus.theme && gameStatus.theme !== currentThemeId) {
    applyTheme(gameStatus.theme, false);
  }

  // Allow clicking news cards to refresh version info
  const newsCyberCard = document.getElementById("news-content-cyber");
  if (newsCyberCard) {
    newsCyberCard.title = "Nhấn để làm mới thông tin Việt Hoá";
    newsCyberCard.style.cursor = "pointer";
    newsCyberCard.addEventListener("click", () => {
      toast("Đang làm mới thông tin Việt Hoá...", "info");
      loadVersion();
      refreshStatus();
    });
  }

  // Auto-update check (only if previously installed version is older than server)
  if (serverInfo && serverInfo.version && gameStatus && gameStatus.has_game) {
    if (gameStatus.vh_version && gameStatus.vh_version !== serverInfo.version) {
      console.log(`Auto-updating from ${gameStatus.vh_version} to ${serverInfo.version}`);
      setTimeout(startUpdate, 1000);
    }
  }
}

init();

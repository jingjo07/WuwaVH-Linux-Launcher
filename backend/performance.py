"""
High Performance Mode Manager for WuWaVH
Safely modifies and manages Unreal Engine 4 SystemSettings in Engine.ini,
DeviceProfiles.ini, and Input.ini with automatic backup and presets from
AlteriaX/WuWa-Configs (https://github.com/AlteriaX/WuWa-Configs).
"""

import os
import shutil
from backend import game
from backend.presets_data import FULL_PRESETS, COMMON_DEVICE_PROFILES_INI, COMMON_INPUT_INI

DEFAULT_PERF_SETTINGS = {
    "enabled": False,
    "active_preset": "config-3",  # default to "config-3" (Vừa lừa)
    # Anti-Lag Toggles
    "world_partition_opt": True,
    "uro_opt": True,
    "async_fx": True,
    "early_z_pass": True,
    "shadow_csm_opt": False,
    "foliage_cull": False,
    # Core Graphics Toggles
    "shadow_off": False,
    "reflection_off": False,
    "postprocess_off": False,
    "grass_off": False,
    "kuro_effects_off": False,
    "force_component_lod": False,
    # Sliders & Select
    "screen_percentage": 100,
    "view_distance_scale": 1.0,
    "static_mesh_lod_scale": 1.0,
    "skeletal_mesh_lod_bias": 0,
    "npc_disappear_dist": 2000,
    "max_anisotropy": 16,
}


def get_engine_ini_path() -> str | None:
    """Return path to Client/Saved/Config/WindowsNoEditor/Engine.ini if game path is detected."""
    game_dir = game.detect_game_path()
    if not game_dir:
        return None
    candidates = [
        os.path.join(game_dir, "Wuthering Waves Game", "Client", "Saved", "Config", "WindowsNoEditor", "Engine.ini"),
        os.path.join(game_dir, "Wuthering Waves Game", "Client", "Saved", "Config", "Windows", "Engine.ini"),
        os.path.join(game_dir, "Client", "Saved", "Config", "WindowsNoEditor", "Engine.ini"),
        os.path.join(game_dir, "Client", "Saved", "Config", "Windows", "Engine.ini"),
    ]
    for c in candidates:
        if os.path.exists(c) or os.path.isdir(os.path.dirname(c)):
            return c
    # Fallback preferred candidate
    if os.path.isdir(os.path.join(game_dir, "Wuthering Waves Game")):
        return os.path.join(game_dir, "Wuthering Waves Game", "Client", "Saved", "Config", "WindowsNoEditor", "Engine.ini")
    return os.path.join(game_dir, "Client", "Saved", "Config", "WindowsNoEditor", "Engine.ini")


def get_dp_ini_path() -> str | None:
    """Return path to Client/Saved/Config/WindowsNoEditor/DeviceProfiles.ini."""
    eng = get_engine_ini_path()
    if eng:
        return os.path.join(os.path.dirname(eng), "DeviceProfiles.ini")
    return None


def get_input_ini_path() -> str | None:
    """Return path to Client/Saved/Config/WindowsNoEditor/Input.ini."""
    eng = get_engine_ini_path()
    if eng:
        return os.path.join(os.path.dirname(eng), "Input.ini")
    return None


def get_backup_ini_path() -> str | None:
    """Return path to Engine.ini.wuwavh_bak."""
    ini_path = get_engine_ini_path()
    if ini_path:
        return ini_path + ".wuwavh_bak"
    return None


def get_backup_dp_path() -> str | None:
    """Return path to DeviceProfiles.ini.wuwavh_bak."""
    dp_path = get_dp_ini_path()
    if dp_path:
        return dp_path + ".wuwavh_bak"
    return None


def get_backup_input_path() -> str | None:
    """Return path to Input.ini.wuwavh_bak."""
    inp_path = get_input_ini_path()
    if inp_path:
        return inp_path + ".wuwavh_bak"
    return None


def _clean_user_engine_ini():
    """Remove obsolete UserEngine.ini as mandated by AlteriaX."""
    game_dir = game.detect_game_path()
    if not game_dir:
        return
    for sub in [
        os.path.join("Wuthering Waves Game", "Client", "Config", "UserEngine.ini"),
        os.path.join("Client", "Config", "UserEngine.ini"),
    ]:
        p = os.path.join(game_dir, sub)
        if os.path.isfile(p):
            try:
                os.remove(p)
                print(f"[Performance] Removed obsolete {p}")
            except Exception as e:
                print(f"[Performance Warning] Could not remove {p}: {e}")


def ensure_backup() -> bool:
    """Create backup of Engine.ini, DeviceProfiles.ini and Input.ini if not already existing."""
    eng_path = get_engine_ini_path()
    eng_bak = get_backup_ini_path()
    if eng_path and os.path.isfile(eng_path) and eng_bak and not os.path.isfile(eng_bak):
        try:
            shutil.copy2(eng_path, eng_bak)
            print(f"[Performance] Created Engine.ini backup at: {eng_bak}")
        except Exception as e:
            print(f"[Performance Warning] Failed to backup Engine.ini: {e}")

    dp_path = get_dp_ini_path()
    dp_bak = get_backup_dp_path()
    if dp_path and os.path.isfile(dp_path) and dp_bak and not os.path.isfile(dp_bak):
        try:
            shutil.copy2(dp_path, dp_bak)
            print(f"[Performance] Created DeviceProfiles.ini backup at: {dp_bak}")
        except Exception as e:
            print(f"[Performance Warning] Failed to backup DeviceProfiles.ini: {e}")

    inp_path = get_input_ini_path()
    inp_bak = get_backup_input_path()
    if inp_path and os.path.isfile(inp_path) and inp_bak and not os.path.isfile(inp_bak):
        try:
            shutil.copy2(inp_path, inp_bak)
            print(f"[Performance] Created Input.ini backup at: {inp_bak}")
        except Exception as e:
            print(f"[Performance Warning] Failed to backup Input.ini: {e}")

    return True


def get_perf_settings() -> dict:
    """Get current performance settings with active preset info and backup state."""
    cfg = game.load_config()
    saved = cfg.get("performance_settings", {})
    settings = dict(DEFAULT_PERF_SETTINGS)
    settings.update(saved)

    # Add presets list for frontend
    presets_summary = []
    for pid, pdata in FULL_PRESETS.items():
        presets_summary.append({
            "id": pid,
            "name": pdata["name"],
            "subtitle": pdata.get("subtitle", ""),
            "group": pdata.get("group", ""),
            "badge": pdata.get("badge", ""),
            "note": pdata.get("note", ""),
            "gpu_info": pdata.get("gpu_info", ""),
        })
    settings["presets"] = presets_summary

    bak_path = get_backup_ini_path()
    settings["has_backup"] = bool(bak_path and os.path.isfile(bak_path))
    return settings


def get_current_engine_ini_text() -> str:
    """Return raw text of current Engine.ini for user inspection."""
    eng_path = get_engine_ini_path()
    if eng_path and os.path.isfile(eng_path):
        try:
            with open(eng_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Lỗi đọc file Engine.ini: {e}"
    return "Chưa tìm thấy file Engine.ini trong thư mục game."


def _get_core_system_lines() -> list:
    """Read existing Core.System paths from backup or current Engine.ini."""
    eng_path = get_engine_ini_path()
    source_ini = get_backup_ini_path()
    if not (source_ini and os.path.isfile(source_ini)):
        source_ini = eng_path

    core_lines = []
    if source_ini and os.path.isfile(source_ini):
        with open(source_ini, "r", errors="ignore") as f:
            in_core = False
            for line in f:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_core = (stripped.lower() == "[core.system]")
                    if in_core:
                        core_lines.append(line)
                    continue
                if in_core:
                    core_lines.append(line)
    return core_lines


def apply_perf_preset(preset_name: str) -> dict:
    """
    Apply configuration from AlteriaX/WuWa-Configs.
    Supports: 'default', 'config-1', 'config-2', 'config-3', 'config-4', 'config-5'.
    """
    preset_name = (preset_name or "config-3").lower()

    if preset_name == "default":
        return restore_default_ini()

    if preset_name not in FULL_PRESETS:
        raise ValueError(f"Không tìm thấy preset: {preset_name}")

    eng_path = get_engine_ini_path()
    dp_path = get_dp_ini_path()
    inp_path = get_input_ini_path()
    if not eng_path:
        raise FileNotFoundError("Không tìm thấy thư mục game để cấu hình Engine.ini.")

    os.makedirs(os.path.dirname(eng_path), exist_ok=True)
    ensure_backup()
    _clean_user_engine_ini()

    preset_data = FULL_PRESETS[preset_name]
    raw_eng = preset_data["engine_ini"]
    raw_dp = preset_data.get("device_profiles_ini", "")
    raw_inp = preset_data.get("input_ini", "")

    # Write Engine.ini directly
    with open(eng_path, "w", encoding="utf-8") as f:
        f.write(raw_eng)
    print(f"[Performance] Applied AlteriaX preset '{preset_name}' to {eng_path}")

    # Write DeviceProfiles.ini if provided
    if dp_path and raw_dp:
        with open(dp_path, "w", encoding="utf-8") as f:
            f.write(raw_dp)
        print(f"[Performance] Applied DeviceProfiles.ini to {dp_path}")

    # Write Input.ini if provided
    if inp_path and raw_inp:
        with open(inp_path, "w", encoding="utf-8") as f:
            f.write(raw_inp)
        print(f"[Performance] Applied Input.ini to {inp_path}")

    # Save to config.json
    cfg = game.load_config()
    cur_perf = cfg.get("performance_settings", {})
    cur_perf["enabled"] = True
    cur_perf["active_preset"] = preset_name
    cfg["performance_settings"] = cur_perf
    game.save_config(cfg)

    return get_perf_settings()


def save_and_apply_perf_settings(new_settings: dict) -> dict:
    """
    Save custom performance settings and write directly to Engine.ini.
    Applies immediately on any toggle or slider change in Advanced mode.
    """
    eng_path = get_engine_ini_path()
    if not eng_path:
        raise FileNotFoundError("Không tìm thấy thư mục game để cấu hình Engine.ini.")

    os.makedirs(os.path.dirname(eng_path), exist_ok=True)
    ensure_backup()
    _clean_user_engine_ini()

    cfg = game.load_config()
    current = dict(DEFAULT_PERF_SETTINGS)
    current.update(cfg.get("performance_settings", {}))
    current.update(new_settings)
    current["active_preset"] = "custom"

    # Write to Engine.ini
    core_lines = _get_core_system_lines()

    sys_cvars = []
    rend_cvars = []

    # 1. Anti-Lag: World Partition
    if current.get("world_partition_opt", True):
        sys_cvars.extend([
            "wp.Runtime.LoadingRangeScale=0.65",
            "wp.Runtime.PlannedLoadingRangeScale=0.8",
        ])

    # 2. Anti-Lag: Animation URO
    if current.get("uro_opt", True):
        sys_cvars.extend([
            "a.URO.Enable=1",
            "a.URO.ForceInterpolation=1",
            "a.URO.ForceAnimRate=2",
        ])

    # 3. Anti-Lag: GPU Async Compute FX
    if current.get("async_fx", True):
        sys_cvars.extend([
            "FX.AllowAsyncTick=1",
            "FX.BatchAsync=1",
            "FX.AllowGPUParticles=1",
            "FX.AllowGPUSorting=1",
            "FX.AllowFastPathFunctionLibrary=1",
            "FX.AllowCulling=1",
        ])

    # 4. Anti-Lag: Early-Z Pass
    if current.get("early_z_pass", True):
        sys_cvars.extend([
            "r.EarlyZPass=3",
            "r.FogVisibilityCulling.Enable=1",
            "r.kuro.ActorCullingVolumeEnable=1",
        ])

    # 5. Shadow CSM
    if current.get("shadow_off", False):
        rend_cvars.extend([
            "r.ShadowQuality=0",
            "r.Shadow.DistanceScale=0",
            "r.ContactShadows=0",
            "r.DistanceFieldShadowing=0",
            "r.CapsuleShadows=0",
            "r.Shadow.CSM.MaxCascades=0",
        ])
    elif current.get("shadow_csm_opt", False):
        rend_cvars.extend([
            "r.Shadow.CSM.MaxCascades=1",
            "r.Shadow.PerObjectShadowCulling=1",
            "r.Shadow.FarShadowDistanceOverride=0",
            "r.Shadow.MinResolution=32",
        ])

    # 6. Foliage
    if current.get("grass_off", False):
        sys_cvars.extend([
            "foliage.DensityScale=0",
            "grass.DensityScale=0",
            "foliage.CullAll=1",
        ])
    elif current.get("foliage_cull", False):
        sys_cvars.extend([
            "foliage.CullAllInVertexShader=1",
            "grass.DisableDynamicShadows=1",
            "r.Kuro.Foliage.EnableFoliageCulling=1",
            "r.Kuro.Foliage.MobileGrassCullDistanceMax=1500",
            "r.Kuro.Foliage.MobileFarCullDistanceMax=2000",
        ])

    # 7. Reflection
    if current.get("reflection_off", False):
        rend_cvars.extend([
            "r.SSR.Quality=0",
            "r.RefractionQuality=0",
            "r.Water.SingleLayer.Reflection=0",
        ])

    # 8. PostProcess
    if current.get("postprocess_off", False):
        rend_cvars.extend([
            "r.MotionBlurQuality=0",
            "r.DepthOfFieldQuality=0",
            "r.BloomQuality=0",
            "r.LensFlareQuality=0",
            "r.SceneColorFringeQuality=0",
            "r.FilmGrain=0",
            "r.Kuro.KuroBloomStreak=0",
            "r.KuroMobile.LensFlareQuality=0",
        ])

    # 9. Kuro Effects
    if current.get("kuro_effects_off", False):
        sys_cvars.extend([
            "r.Kuro.VolumetricFog=0",
            "r.Kuro.VolumetricCloud=0",
        ])

    # 10. Force Component LOD
    if current.get("force_component_lod", False):
        sys_cvars.append("r.ForceComponentLOD=1")

    # 11. Sliders
    screen_pct = current.get("screen_percentage", 100)
    sys_cvars.append(f"r.ScreenPercentage={int(screen_pct)}")

    view_dist = current.get("view_distance_scale", 1.0)
    sys_cvars.append(f"r.ViewDistanceScale={float(view_dist):.2f}")

    static_lod = current.get("static_mesh_lod_scale", 1.0)
    sys_cvars.append(f"r.StaticMeshLODDistanceScale={float(static_lod):.2f}")

    skel_lod = current.get("skeletal_mesh_lod_bias", 0)
    sys_cvars.append(f"r.SkeletalMeshLODBias={int(skel_lod)}")

    npc_dist = current.get("npc_disappear_dist", 2000)
    sys_cvars.append(f"r.NpcDisappearDistance={int(npc_dist)}")

    max_aniso = current.get("max_anisotropy", 16)
    sys_cvars.append(f"r.MaxAnisotropy={int(max_aniso)}")

    # Anti-stutter streaming
    sys_cvars.extend([
        "r.Streaming.LimitPoolSizeToVRAM=1",
        "r.Streaming.PoolSize=0",
    ])

    with open(eng_path, "w", encoding="utf-8") as f:
        if core_lines:
            f.writelines(core_lines)
            f.write("\n")

        if sys_cvars:
            f.write("[SystemSettings]\n")
            for line in sys_cvars:
                f.write(f"{line}\n")
            f.write("\n")

        if rend_cvars:
            f.write("[/Script/Engine.RendererSettings]\n")
            for line in rend_cvars:
                f.write(f"{line}\n")
            f.write("\n")

    cfg["performance_settings"] = current
    game.save_config(cfg)
    print(f"[Performance] Auto-saved custom settings to {eng_path}")

    return get_perf_settings()


def restore_default_ini() -> dict:
    """Restore original Engine.ini, DeviceProfiles.ini and Input.ini from backup."""
    eng_path = get_engine_ini_path()
    eng_bak = get_backup_ini_path()
    dp_path = get_dp_ini_path()
    dp_bak = get_backup_dp_path()
    inp_path = get_input_ini_path()
    inp_bak = get_backup_input_path()

    if eng_path and eng_bak and os.path.isfile(eng_bak):
        try:
            shutil.copy2(eng_bak, eng_path)
            print(f"[Performance] Restored Engine.ini from {eng_bak}")
        except Exception as e:
            print(f"[Performance Warning] Error restoring Engine.ini: {e}")
    elif eng_path and os.path.isfile(eng_path):
        try:
            os.remove(eng_path)
        except Exception:
            pass

    if dp_path:
        if dp_bak and os.path.isfile(dp_bak):
            try:
                shutil.copy2(dp_bak, dp_path)
                print(f"[Performance] Restored DeviceProfiles.ini from {dp_bak}")
            except Exception as e:
                print(f"[Performance Warning] Error restoring DeviceProfiles.ini: {e}")
        elif os.path.isfile(dp_path):
            try:
                os.remove(dp_path)
            except Exception:
                pass

    if inp_path:
        if inp_bak and os.path.isfile(inp_bak):
            try:
                shutil.copy2(inp_bak, inp_path)
                print(f"[Performance] Restored Input.ini from {inp_bak}")
            except Exception as e:
                print(f"[Performance Warning] Error restoring Input.ini: {e}")
        elif os.path.isfile(inp_path):
            try:
                os.remove(inp_path)
            except Exception:
                pass

    # Reset in config.json
    cfg = game.load_config()
    cfg["performance_settings"] = {
        "enabled": False,
        "active_preset": "default",
    }
    game.save_config(cfg)

    return get_perf_settings()

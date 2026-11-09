#!/usr/bin/env python3
"""
tools/sync_from_drive.py
Synchronizes generated AI assets from Google Drive (AI_GameDev_Bridge)
into the local Godot 4 project directory.
"""

import os
import sys
import shutil
import json
import subprocess
from pathlib import Path

# Safe encoding for Windows consoles (e.g. CP949)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def resolve_bridge_path(project_root: Path) -> Path:
    """Finds active Google Drive bridge directory."""
    config_file = project_root / "config" / "bridge_config.json"
    candidate_paths = []

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = data.get("gdrive_bridge_path")
                if custom:
                    p = Path(custom)
                    if not p.is_absolute():
                        p = project_root / p
                    candidate_paths.append(p)
                for c in data.get("default_windows_gdrive_candidates", []):
                    expanded = os.path.expanduser(os.path.expandvars(c))
                    candidate_paths.append(Path(expanded))
        except Exception as e:
            print(f"[Warning] Failed to read config: {e}")

    # Standard fallbacks
    user_home = Path.home()
    candidate_paths.extend([
        Path("G:/내 드라이브/AI_GameDev_Bridge"),
        Path("G:/My Drive/AI_GameDev_Bridge"),
        user_home / "Google Drive" / "AI_GameDev_Bridge",
        project_root / "_gdrive_mock" / "AI_GameDev_Bridge"
    ])

    for p in candidate_paths:
        if p.exists() and p.is_dir():
            return p.resolve()

    # Fallback to mock directory
    mock_dir = project_root / "_gdrive_mock" / "AI_GameDev_Bridge"
    mock_dir.mkdir(parents=True, exist_ok=True)
    return mock_dir.resolve()


def sync_assets():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    bridge_root = resolve_bridge_path(project_root)
    print(f"[*] Active Bridge Root: {bridge_root}")

    raw_renders_dir = bridge_root / "outputs" / "raw_renders"
    maps_2d_dir = bridge_root / "outputs" / "maps_2d"

    art_2d_dir = project_root / "godot_project" / "assets" / "art_2d"
    terrain_3d_dir = project_root / "godot_project" / "assets" / "terrain_3d"

    art_2d_dir.mkdir(parents=True, exist_ok=True)
    terrain_3d_dir.mkdir(parents=True, exist_ok=True)

    # 1. Sync raw_renders -> godot_project/assets/art_2d/
    if raw_renders_dir.exists():
        raw_files = [f for f in raw_renders_dir.iterdir() if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]]
        print(f"[*] Found {len(raw_files)} 2D render(s) in {raw_renders_dir.name}")
        synced_art = 0
        for src in raw_files:
            dst = art_2d_dir / src.name
            if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                print(f"  [+] Synced Character/Art: {src.name} -> art_2d/")
                synced_art += 1
        if synced_art == 0 and raw_files:
            print("  [-] All 2D render assets are already up-to-date.")
    else:
        print(f"[-] Directory not found: {raw_renders_dir}")

    # 2. Sync maps_2d -> heightmap_converter -> godot_project/assets/terrain_3d/
    if maps_2d_dir.exists():
        map_files = [f for f in maps_2d_dir.iterdir() if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]]
        print(f"[*] Found {len(map_files)} 2D terrain map(s) in {maps_2d_dir.name}")
        converter_script = script_dir / "heightmap_converter.py"

        for src in map_files:
            expected_h = terrain_3d_dir / f"{src.stem}_heightmap.png"
            expected_n = terrain_3d_dir / f"{src.stem}_normalmap.png"

            needs_conversion = (
                not expected_h.exists() or
                not expected_n.exists() or
                src.stat().st_mtime > expected_h.stat().st_mtime
            )

            if needs_conversion:
                print(f"  [~] Converting 2D Map: {src.name} -> Heightmap & Normalmap...")
                cmd = [
                    sys.executable,
                    str(converter_script),
                    "--input", str(src),
                    "--output", str(terrain_3d_dir)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    print(f"  [+] Success: {expected_h.name}, {expected_n.name}")
                else:
                    print(f"  [!] Error converting {src.name}:\n{res.stderr}", file=sys.stderr)
            else:
                print(f"  [-] Up-to-date: {src.stem} terrain assets")
    else:
        print(f"[-] Directory not found: {maps_2d_dir}")

    print("\n[OK] Sync process completed.")


if __name__ == "__main__":
    sync_assets()

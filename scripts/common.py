"""Shared helpers for the AI Video Editor pipeline. No hardcoded absolute paths: everything is
resolved relative to the workspace root (parent of scripts/)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw footage"
REFS = ROOT / "references"
EXPORTS = ROOT / "exports"
PROJECTS = ROOT / "projects"
STYLES = ROOT / "styles"
ENGINE = ROOT / "engine"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}


def die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kw)


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def summarize_probe(path: Path) -> dict:
    p = ffprobe(path)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    info = {"file": path.name, "duration": float(p["format"].get("duration", 0)), "size_mb": round(int(p["format"].get("size", 0)) / 1e6, 1)}
    if v:
        num, den = (v.get("avg_frame_rate") or "0/1").split("/")
        rnum, rden = (v.get("r_frame_rate") or "0/1").split("/")
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        if abs(rot) in (90, 270):
            w, h = h, w
        avg = float(num) / float(den) if float(den) else 0
        rf = float(rnum) / float(rden) if float(rden) else 0
        info.update(width=w, height=h, fps=round(avg, 3), vfr=abs(avg - rf) > 0.05, vcodec=v["codec_name"],
                    pix_fmt=v.get("pix_fmt"), rotation=rot, color_transfer=v.get("color_transfer"))
    if a:
        info.update(acodec=a["codec_name"], sample_rate=int(a.get("sample_rate", 0)), channels=a.get("channels"))
    info["has_audio"] = a is not None
    return info


def project_dir(name: str, create: bool = False) -> Path:
    d = PROJECTS / name
    if create:
        for sub in ("public/media", "public/assets/sfx", "public/assets/music", "public/assets/broll", "analysis/transcripts", "renders"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        # shared SFX library -> project public dir (Remotion serves only one public dir)
        lib = STYLES / "assets" / "sfx"
        if lib.exists():
            for f in lib.iterdir():
                if f.is_file():
                    shutil.copy2(f, d / "public/assets/sfx" / f.name)
    elif not d.exists():
        die(f"project not found: {d}")
    return d


def load_style(project: Path | None = None) -> dict:
    style = json.loads((STYLES / "design-system.json").read_text())
    if project and (project / "style.override.json").exists():
        deep_merge(style, json.loads((project / "style.override.json").read_text()))
    return style


def deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path: Path):
    return json.loads(path.read_text())

#!/usr/bin/env python3
"""Prepare projector-sized local copies; leave the personal photo library untouched."""
from pathlib import Path
import glob
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = Path.home() / "Pictures/Wallpapers"
destination = ROOT / "private/wallpapers"
matches = sorted(glob.glob("/nix/store/*-imagemagick-*/bin/magick"))
magick = shutil.which("magick") or (matches[0] if matches else None)
if not magick:
    raise SystemExit("ImageMagick is required to prepare wallpapers")
destination.mkdir(parents=True, exist_ok=True)
report = []
for path in sorted(source.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    output = destination / (path.stem + "-" + digest[:8] + ".webp")
    if not output.exists():
        with tempfile.TemporaryDirectory(dir=destination) as temporary:
            pending = Path(temporary) / "wallpaper.webp"
            subprocess.run([magick, "-quiet", str(path) + "[0]", "-auto-orient", "-resize", "1920x1080^",
                            "-gravity", "center", "-extent", "1920x1080", "-strip", "-quality", "82",
                            str(pending)], check=True, env=dict(os.environ, MAGICK_THREAD_LIMIT="2"))
            os.replace(pending, output)
    report.append({"source": str(path), "source_sha256": digest, "prepared": output.name,
                   "prepared_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
(destination / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"Prepared {len(report)} wallpapers; {sum(p.stat().st_size for p in destination.glob('*.webp')) / 1048576:.1f} MiB")

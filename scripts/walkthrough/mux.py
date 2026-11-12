"""Lay each chapter's narration onto the recording at the moment that chapter began.

Usage: python scripts/walkthrough/mux.py <take dir> <audio dir> <output.mp4>
The take dir holds walkthrough.mkv (screen capture) or .webm and marks.json from record.mjs.
"""

import json
import subprocess
import sys
from pathlib import Path

LEAD_IN = 0.6  # seconds after a chapter starts before its narration begins

take, audio, output = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
marks = json.loads((take / "marks.json").read_text(encoding="utf-8"))

video = next(p for p in (take / "walkthrough.mkv", take / "walkthrough.webm") if p.exists())
inputs = ["-i", str(video)]
filters = []
for i, mark in enumerate(marks, start=1):
    inputs += ["-i", str(audio / f"{mark['id']}.wav")]
    delay = int((mark["at"] + LEAD_IN) * 1000)
    filters.append(f"[{i}:a]adelay={delay}|{delay},aresample=48000[a{i}]")
mix = "".join(f"[a{i}]" for i in range(1, len(marks) + 1))
filters.append(f"{mix}amix=inputs={len(marks)}:normalize=0:dropout_transition=0,volume=1.6,apad[aout]")

subprocess.run(
    [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-r", "25", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "-shortest", output,
    ],
    check=True,
)
print("written", output)

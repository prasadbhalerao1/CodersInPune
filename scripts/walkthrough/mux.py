"""Lay each sentence of narration onto the recording at the moment its beat began.

Where the screen is only waiting after a sentence has ended (an AI answer, a slow page),
that stretch is played as a short time-lapse instead of dead air; everything else,
and every sentence, stays at real speed. A faint room tone runs underneath.

Usage: python scripts/walkthrough/mux.py <take dir> <voice dir> <output.mp4>
The take dir holds walkthrough.mkv and marks.json from record.mjs; the voice dir holds
one <id>.wav per beat and timing.json from voice.py.
"""

import json
import subprocess
import sys
from pathlib import Path

KEEP = 0.8  # seconds of real time kept on each side of a wait
LONGEST_WAIT = 3.0  # waits longer than this are fast-forwarded
WAIT_PLAYS_FOR = 1.5  # how long a fast-forwarded wait lasts in the cut

take, voice, output = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
marks = json.loads((take / "marks.json").read_text(encoding="utf-8"))
timing = json.loads((voice / "timing.json").read_text(encoding="utf-8"))
video = take / "walkthrough.mkv"
length = float(
    subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]
    )
)

# Segments of the recording as (start, end, speed).
segments: list[tuple[float, float, float]] = []
cursor = 0.0
for mark, after in zip(marks, [*(m["at"] for m in marks[1:]), length]):
    spoken_until = mark["at"] + timing[mark["id"]]["dur"]
    wait_from, wait_to = spoken_until + KEEP, after - KEEP
    if wait_to - wait_from > LONGEST_WAIT:
        segments.append((cursor, wait_from, 1.0))
        segments.append((wait_from, wait_to, (wait_to - wait_from) / WAIT_PLAYS_FOR))
        cursor = wait_to
# Open-ended, so sentences timed after the last frame keep their real spacing.
segments.append((cursor, float("inf"), 1.0))


def cut_time(t: float) -> float:
    """Where moment t of the recording lands in the cut."""
    out = 0.0
    for start, end, speed in segments:
        if t <= start:
            break
        out += (min(t, end) - start) / speed
    return out


# The screencast stops at the last change on screen; hold that frame until the last word.
spoken_end = cut_time(marks[-1]["at"]) + timing[marks[-1]["id"]]["dur"] + 1.5
hold = max(0.0, spoken_end - cut_time(length))

n = len(segments)
filters = [f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n))]
for i, (start, end, speed) in enumerate(segments):
    filters.append(f"[s{i}]trim={start:.3f}:{min(end, length):.3f},setpts=(PTS-STARTPTS)/{speed:.4f}[v{i}]")
filters.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,tpad=stop_mode=clone:stop_duration={hold:.2f},fps=25[vout]")

inputs = ["-i", str(video)]
for i, mark in enumerate(marks, start=1):
    inputs += ["-i", str(voice / f"{mark['id']}.wav")]
    delay = int(cut_time(mark["at"]) * 1000)
    filters.append(f"[{i}:a]adelay={delay}|{delay},aresample=48000[a{i}]")
total = cut_time(length) + hold
filters.append(
    f"anoisesrc=color=brown:amplitude=0.004:sample_rate=48000:duration={total:.2f},lowpass=f=900[room]"
)
mix = "".join(f"[a{i}]" for i in range(1, len(marks) + 1))
filters.append(
    f"{mix}[room]amix=inputs={len(marks) + 1}:normalize=0:dropout_transition=0:duration=longest,volume=1.4[aout]"
)

script = take / "mux-filter.txt"
script.write_text(";\n".join(filters), encoding="utf-8")
subprocess.run(
    [
        "ffmpeg", "-y", *inputs,
        "-filter_complex_script", str(script),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart",
        "-t", f"{total:.2f}", output,
    ],
    check=True,
)
print(f"written {output}: {total / 60:.1f} min, {sum(1 for s in segments if s[2] > 1)} waits fast-forwarded")

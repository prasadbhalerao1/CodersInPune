"""Voice every beat with a neural voice and record when its cue words are spoken.

A beat's text may mark words with ^ ("I'll click ^Insights"). The recorder fires that
beat's actions at those moments, so a click lands on the word that names it.

Usage: python voice.py <narration.json> <out dir> [voice]
Writes <out>/<id>.wav for each beat and <out>/timing.json: {id: {"dur": s, "cues": [s, ...]}}.
Needs edge-tts and ffmpeg.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import aiohttp
import edge_tts

narration, out = Path(sys.argv[1]), Path(sys.argv[2])
voice = sys.argv[3] if len(sys.argv) > 3 else "en-US-AndrewMultilingualNeural"
out.mkdir(parents=True, exist_ok=True)


def cue_offsets(marked: str) -> tuple[str, list[int]]:
    """The text without markers, and the character offset of each marked word."""
    clean, cues = [], []
    for ch in marked:
        if ch == "^":
            cues.append(len(clean))
        else:
            clean.append(ch)
    return "".join(clean), cues


async def speak(beat: dict) -> dict:
    text, cues = cue_offsets(beat["text"])
    mp3 = out / f"{beat['id']}.mp3"
    words = []  # (char offset in text, seconds)
    pos = 0
    with mp3.open("wb") as audio:
        async for chunk in edge_tts.Communicate(text, voice, boundary="WordBoundary").stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                found = text.find(chunk["text"], pos)
                if found >= 0:
                    words.append((found, chunk["offset"] / 1e7))
                    pos = found + len(chunk["text"])
    wav = out / f"{beat['id']}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "48000", "-ac", "1", wav], check=True)
    mp3.unlink()
    dur = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]
        )
    )
    at = [next((s for o, s in words if o >= c), dur) for c in cues]
    return {"dur": round(dur, 3), "cues": [round(s, 3) for s in at]}


async def speak_with_retry(beat: dict) -> dict:
    # The voice service occasionally drops a request; a short backoff is enough.
    for attempt in range(5):
        try:
            return await speak(beat)
        except (edge_tts.exceptions.EdgeTTSException, aiohttp.ClientError):
            if attempt == 4:
                raise
            await asyncio.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


async def main() -> None:
    beats = json.loads(narration.read_text(encoding="utf-8"))
    # A beat whose text is unchanged since the last run keeps its audio.
    saved = out / "timing.json"
    old = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {}
    timing = {}
    for beat in beats:
        prev = old.get(beat["id"])
        if prev and prev.get("text") == beat["text"] and (out / f"{beat['id']}.wav").exists():
            timing[beat["id"]] = prev
        else:
            timing[beat["id"]] = {**await speak_with_retry(beat), "text": beat["text"]}
        saved.write_text(json.dumps(timing, indent=1), encoding="utf-8")
    print(len(timing), "beats,", round(sum(t["dur"] for t in timing.values()) / 60, 1), "min")


asyncio.run(main())

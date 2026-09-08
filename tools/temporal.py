"""FFmpeg media preparation. Authored pauses are distinct from insufficient footage."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from common import ffprobe, find_executable, project_file, run, write_json, read_json


def cache_key(source: Path, settings: dict) -> str:
    stat = source.stat()
    return hashlib.sha256(json.dumps([str(source.resolve()), stat.st_size, stat.st_mtime_ns, settings], sort_keys=True).encode()).hexdigest()[:24]


def tighten_speech(root, path, seconds, params, captions):
    """Only remove measured leading/trailing silence, retaining a breath margin.

    Internal pauses and phonemes are never removed. The original TTS cache is untouched.
    """
    source = project_file(root, path)
    key = cache_key(source, {"tighten-v1": params})
    target = root / f"work/temporal/{key}.wav"
    receipt = target.with_suffix(".json")
    if receipt.is_file() and target.is_file():
        data = read_json(receipt)
    else:
        result = run([find_executable("ffmpeg"), "-hide_banner", "-i", source, "-vn", "-af",
                      f"silencedetect=noise={params['threshold_db']}dB:d=0.08", "-f", "null", "-"], capture=True)
        intervals, start = [], None
        for kind, value in re.findall(r"silence_(start|end):\s*([0-9.]+)", result.stderr):
            if kind == "start":
                start = float(value)
            elif start is not None:
                intervals.append((start, float(value)))
                start = None
        if start is not None:
            intervals.append((start, seconds))
        begin, end = 0.0, seconds
        for a, b in intervals:
            if a <= 0.005:
                begin = max(0, b - params["keep"])
            if b >= seconds - 0.025:
                end = min(seconds, a + params["keep"])
        if end - begin < 0.08:
            raise ValueError(f"jump_cut_tighten: 発話が無音または短すぎます: {path}")
        # Trusted character alignment is an additional guard against clipping voiced text.
        if captions:
            voiced = [c for c in captions if c["text"].strip()]
            begin = min(begin, max(0, min(c["startMs"] for c in voiced) / 1000 - params["keep"]))
            end = max(end, min(seconds, max(c["endMs"] for c in voiced) / 1000 + params["keep"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        run([find_executable("ffmpeg"), "-v", "error", "-y", "-i", source, "-vn", "-af",
             f"atrim=start={begin:.9f}:end={end:.9f},asetpts=PTS-STARTPTS", "-ar", "48000", "-c:a", "pcm_s16le", target], capture=True)
        data = {"source": path, "trim_start": begin, "trim_end": seconds - end,
                "duration": float(ffprobe(target)["format"]["duration"])}
        write_json(receipt, data)
    shifted = None if captions is None else [{**c, "startMs": max(0, c["startMs"] - data["trim_start"] * 1000),
                                              "endMs": min(data["duration"] * 1000, max(0, c["endMs"] - data["trim_start"] * 1000)),
                                              "timestampMs": None} for c in captions]
    return target.relative_to(root).as_posix(), data["duration"], shifted, data


def ramp_segments(length, fps, events, base_speed=1):
    """Piecewise-linear source/output map, with a cosine speed envelope every frame.

    setpts uses the inverse of this monotonic map; no source frame is looped.
    """
    knots = {0, length}
    for e in events:
        knots.update(range(e["local_from"], e["local_to"] + 1))
    knots = sorted(knots)
    source, segments = 0.0, []
    for a, b in zip(knots, knots[1:]):
        midpoint = (a + b) / 2
        rate = base_speed
        for e in events:
            if e["local_from"] <= midpoint < e["local_to"]:
                t = (midpoint - e["local_from"]) / (e["local_to"] - e["local_from"])
                peak = 1 + (e["params"]["peak"] - 1) * e["intensity"] / 0.5
                rate *= 1 + (peak - 1) * math.sin(math.pi * t) ** 2
        consumed = (b - a) / fps * rate
        segments.append({"source_from": source, "source_to": source + consumed, "output_from": a / fps, "speed": rate})
        source += consumed
    return segments, source


def prepare_cues(root, cues):
    """Apply millisecond SFX fades in samples, not frame-stepped volume callbacks.

    A 3ms fade evaluated at 30fps can otherwise mute a click's first frame.
    Source markers and timeline placement stay unchanged.
    """
    for cue in cues:
        source = project_file(root, cue['path'])
        length = cue['source_duration']
        settings = {'sfx-v1': True, 'start': cue['source_start'], 'duration': length, 'fade_in': .003, 'fade_out': .01}
        target = root / f'work/temporal/{cache_key(source, settings)}.wav'
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix('.tmp.wav')
            run([find_executable('ffmpeg'), '-v', 'error', '-y', '-ss', str(cue['source_start']), '-i', source,
                 '-t', str(length), '-vn', '-af', f'afade=t=in:d=0.003,afade=t=out:st={max(0, length - .01):.9f}:d=0.01',
                 '-ar', '48000', '-c:a', 'pcm_s16le', temporary], capture=True)
            temporary.replace(target)
            write_json(target.with_suffix('.json'), {'source': cue['path'], **settings})
        cue['original_path'], cue['original_source_start'] = cue['path'], cue['source_start']
        cue.update(path=target.relative_to(root).as_posix(), source_start=0)


def prepare_ramps(root, shots, events, fps):
    for shot in shots:
        ramps = [e for e in events if e["effect"] == "speed_ramp" and e["target"].get("shot") == shot["id"]]
        if not ramps:
            continue
        for e in ramps:
            e.update(local_from=e["from"] - shot["from"], local_to=e["to"] - shot["from"])
        ramps.sort(key=lambda e: e["from"])
        if any(b["from"] < a["to"] for a, b in zip(ramps, ramps[1:])):
            raise ValueError("同じショットのspeed_rampは重複できません")
        count = shot["to"] - shot["from"]
        segments, consumed = ramp_segments(count, fps, ramps, shot["speed"])
        source = project_file(root, shot["path"])
        available = float(ffprobe(source)["format"]["duration"])
        if shot["source_start"] + consumed > available:
            raise ValueError(f"speed_ramp: 動画素材の尺が足りません: {shot['id']} (必要 {consumed:.3f}s)")
        key = cache_key(source, {"ramp-v1": segments, "start": shot["source_start"], "fps": fps, "count": count})
        target = root / f"work/temporal/{key}.mp4"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            expression = ""
            for s in reversed(segments):
                part = f"({s['output_from']:.9f}+(T-{s['source_from']:.9f})/{s['speed']:.9f})"
                expression = part if not expression else f"if(lt(T,{s['source_to']:.9f}),{part},{expression})"
            temporary = target.with_suffix(".tmp.mp4")
            run([find_executable("ffmpeg"), "-v", "error", "-y", "-ss", str(shot["source_start"]),
                 "-i", source, "-an", "-vf", f"setpts='{expression}/TB',fps={fps},trim=end_frame={count},setpts=PTS-STARTPTS",
                 "-frames:v", str(count), "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", temporary], capture=True)
            info = ffprobe(temporary)
            stream = next(s for s in info["streams"] if s["codec_type"] == "video")
            if int(stream.get("nb_frames", 0)) != count:
                raise ValueError("speed_rampの出力フレーム数が一致しません")
            temporary.replace(target)
            write_json(target.with_suffix(".json"), {"source": shot["path"], "source_start": shot["source_start"], "consumed_seconds": consumed, "segments": segments, "frames": count})
        shot["original_path"], shot["original_source_start"] = shot["path"], shot["source_start"]
        shot.update(path=target.relative_to(root).as_posix(), source_start=0, speed=1)

"""Resolve ordinary edit decisions to frames; editorial judgment stays in the project."""
from __future__ import annotations

import math
from pathlib import Path

from common import ffprobe, project_file


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{label}: {minimum}以上の有限数が必要です")
    return float(value)


def frame(seconds, fps):
    return math.floor(seconds * fps + 0.5)


def resolve_time(value, lines, duration):
    if value is None:
        return duration
    if isinstance(value, (float, int)):
        return number(value, "time")
    if not isinstance(value, dict) or value.get("line") not in lines or value.get("edge", "start") not in {"start", "end"}:
        raise ValueError(f"不正な発話参照: {value}")
    return lines[value["line"]][value.get("edge", "start")] + number(value.get("offset", 0), "offset", -1e6)


def timed_event(event, lines, duration, fps):
    start = resolve_time(event.get("from", 0), lines, duration)
    end = resolve_time(event.get("to"), lines, duration)
    if start < 0 or end > duration + 1e-6 or end <= start:
        raise ValueError(f"編集区間が動画の範囲外です: {start:.3f}..{end:.3f} / {duration:.3f}")
    first, last = frame(start, fps), frame(end, fps)
    if last <= first:
        raise ValueError("編集区間が1フレーム未満です")
    return {**event, "from": first, "to": last}


def media_info(root, path, cache):
    if not isinstance(path, str):
        raise ValueError("素材pathが必要です")
    file = project_file(root, path)
    if not file.is_file():
        raise ValueError(f"素材がありません: {path}")
    if path not in cache:
        cache[path] = ffprobe(file)
    return cache[path]


def camera_points(points):
    points = points or [{"at": 0, "x": 0.5, "y": 0.5, "zoom": 1}]
    previous = -1
    for p in points:
        at = number(p.get("at"), "camera.at")
        if at > 1 or at <= previous:
            raise ValueError("camera.atは0..1の昇順で指定してください")
        previous = at
        for key in ("x", "y"):
            if number(p.get(key, 0.5), f"camera.{key}") > 1:
                raise ValueError("camera.x/yは素材上の0..1の位置です")
        number(p.get("zoom", 1), "camera.zoom", 1)
    return [{"x": 0.5, "y": 0.5, "zoom": 1, **p} for p in points]


def compile_edit(root, project, lines, duration, fps):
    cache = {}
    shots, audio = [], []
    previous_end = 0
    ids = set()
    for index, shot in enumerate(project["shots"]):
        item = timed_event(shot, lines, duration, fps)
        item["id"] = shot.get("id", f"shot-{index + 1}")
        if item["id"] in ids:
            raise ValueError(f"shot.idが重複しています: {item['id']}")
        ids.add(item["id"])
        if item["from"] != previous_end:
            raise ValueError(f"{item['id']}: 映像に空白または重複があります ({previous_end} -> {item['from']})")
        previous_end = item["to"]
        info = media_info(root, item.get("path"), cache)
        stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        if not stream:
            raise ValueError(f"映像がありません: {item['path']}")
        item["media"] = "image" if Path(item["path"]).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else "video"
        item["source_width"], item["source_height"] = stream["width"], stream["height"]
        # Rotation metadata makes source-space framing ambiguous. Normalize such footage first.
        if any(abs(s.get("rotation", 0)) % 360 for s in stream.get("side_data_list", [])) or int(stream.get("tags", {}).get("rotate", 0)) % 360:
            raise ValueError(f"回転メタデータ付き素材はFFmpegで正立化してください: {item['path']}")
        sar = stream.get("sample_aspect_ratio", "1:1")
        if sar not in {"1:1", "0:1", "N/A"}:
            raise ValueError(f"非正方形ピクセル素材はFFmpegでsetsar=1に変換してください: {item['path']}")
        item["source_start"] = frame(number(item.get("source_start", 0), "source_start"), fps) / fps
        rate = number(item.get("speed", 1), "speed", 0.01)
        item["speed"] = rate
        if item["media"] == "video":
            needed = item["source_start"] + (item["to"] - item["from"]) / fps * rate
            if needed > float(info["format"]["duration"]) + 1 / fps:
                raise ValueError(f"動画素材の尺が足りません（ループ・静止延長しません）: {item['path']}")
        item["camera"] = camera_points(item.get("camera"))
        if item.get("fit", "cover") not in {"cover", "contain"}:
            raise ValueError("fitはcoverまたはcontainです")
        shots.append(item)
    if previous_end != frame(duration, fps):
        raise ValueError("動画の末尾まで映像がありません")
    for sound in project.get("audio", []):
        item = timed_event(sound, lines, duration, fps)
        info = media_info(root, item.get("path"), cache)
        if not any(s["codec_type"] == "audio" for s in info["streams"]):
            raise ValueError(f"音声がありません: {item['path']}")
        for key in ("loop", "duck"):
            if key in item and not isinstance(item[key], bool):
                raise ValueError(f"audio.{key}はtrue/falseです")
        source = frame(number(item.get("source_start", 0), "audio.source_start"), fps) / fps
        item["source_start"] = source
        length = float(info["format"]["duration"])
        if source >= length or (not item.get("loop") and source + (item["to"] - item["from"]) / fps > length + 1 / fps):
            raise ValueError(f"音素材の尺が足りません: {item['path']}")
        for key in ("volume", "fade_in", "fade_out"):
            if key in item:
                number(item[key], "audio." + key)
        audio.append(item)
    return shots, audio

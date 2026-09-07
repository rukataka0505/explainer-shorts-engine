from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from common import REPO_ROOT, ffprobe, final_output_path, find_executable, project_file, read_json, run, write_json
from speech import Voicevox, ElevenLabs, synthesize, synthesize_elevenlabs
from edit import compile_edit, frame, number


def load_project(root: Path) -> dict:
    project = read_json(root / "project.json")
    if not isinstance(project.get("title"), str) or not project["title"].strip():
        raise ValueError("titleが必要です")
    if "scenes" in project or not isinstance(project.get("beats"), list) or not project["beats"]:
        raise ValueError("新形式のbeatsが必要です。旧形式の移行機能はありません")
    voices = project.get("voices", {"narrator": dict(read_json(REPO_ROOT / "style.json")["voice"])})
    if not isinstance(voices, dict) or not voices:
        raise ValueError("voicesが空です")
    for name, voice in voices.items():
        provider = voice.setdefault("provider", "voicevox" if "style_id" in voice else "elevenlabs")
        if provider == "elevenlabs":
            defaults = read_json(REPO_ROOT / "style.json")["voice"]
            voices[name] = {**defaults, **voice}
            if not isinstance(voices[name]["voice_id"], str) or not voices[name]["voice_id"].strip():
                raise ValueError("ElevenLabs voice_idが必要です")
        elif provider == "voicevox":
            if not isinstance(voice.get("style_id"), int) or isinstance(voice["style_id"], bool):
                raise ValueError(f"voices.{name}.style_idはVOICEVOXの整数IDです")
        else:
            raise ValueError(f"未対応の音声provider: {provider}")
    ids: set[str] = set()
    for beat in project["beats"]:
        for item in [beat, *beat.get("lines", [])]:
            key = item.get("id", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", key) or key in ids:
                raise ValueError(f"IDは全体で一意の英数字・ハイフン・下線にしてください: {key}")
            ids.add(key)
        if not beat.get("lines") and "duration" not in beat:
            raise ValueError(f"{beat['id']}: 無言のbeatにはdurationが必要です")
        if "duration" in beat:
            number(beat["duration"], beat["id"] + ".duration", 0.001)
        for line in beat.get("lines", []):
            if not isinstance(line.get("text"), str) or not line["text"].strip():
                raise ValueError(f"{line['id']}: textが必要です")
            if len(voices) > 1 and "voice" not in line:
                raise ValueError(f"{line['id']}: 複数音声ではvoiceを指定してください")
            if line.get("voice", next(iter(voices))) not in voices:
                raise ValueError(f"{line['id']}: 未定義のvoiceです")
            if "gap" in line:
                number(line["gap"], line["id"] + ".gap")

    if not isinstance(project.get("shots"), list) or not project["shots"]:
        raise ValueError("shotsが必要です")
    project["voices"] = voices
    final_output_path(root, project)
    return project


def asset(root: Path, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("素材pathは文字列です")
    path = project_file(root, value)
    if not path.is_file():
        raise ValueError(f"素材がありません: {value}")
    return path.relative_to(root).as_posix()


def prepare(root: Path, project: dict, client=None) -> dict:
    style = read_json(REPO_ROOT / "style.json")
    video = {**style["video"], **project.get("video", {})}
    for key in ("width", "height", "fps"):
        number(video[key], key, 1)
        if int(video[key]) != video[key]:
            raise ValueError(f"{key}は整数です")
    if video["width"] % 2 or video["height"] % 2 or abs(video["width"] / video["height"] - 9 / 16) > 0.001:
        raise ValueError("Shortsは偶数解像度の9:16です")
    fps = video["fps"]
    cursor = 0.0
    records, beats, anchors = [], [], {}
    reused = generated = 0
    for beat in project["beats"]:
        begin = cursor
        for line in beat.get("lines", []):
            captions = None
            if "path" in line:
                path = asset(root, line["path"])
                info = ffprobe(root / path)
                if not any(s["codec_type"] == "audio" for s in info["streams"]):
                    raise ValueError(f"ナレーション音声がありません: {path}")
                seconds = float(info["format"]["duration"])
                voice_name = line.get("credit", "recorded narration")
            else:
                voice = project["voices"][line.get("voice", next(iter(project["voices"])))]
                if voice["provider"] == "elevenlabs":
                    settings = {**style["voice"]["settings"], **voice.get("settings", {}), **line.get("settings", {})}
                    record, cached = synthesize_elevenlabs(ElevenLabs(), root / "work" / "audio", line["text"], voice, settings)
                    captions = record["captions"]
                else:
                    client = client or Voicevox()
                    settings = {**style["voicevox"]["settings"], **voice.get("settings", {}), **line.get("settings", {})}
                    record, cached = synthesize(client, root / "work" / "audio", line["text"], voice["style_id"], settings)
                reused += int(cached)
                generated += int(not cached)
                seconds, voice_name = record["duration"], record["name"]
                path = Path(record["path"]).relative_to(root).as_posix()
            # Quantize narration once: anchors and playback share exactly the same frames.
            first = frame(cursor, fps)
            last = first + math.ceil(seconds * fps)
            anchors[line["id"]] = {"start": first / fps, "end": last / fps}
            records.append({"id": line["id"], "beat": beat["id"], "text": line["text"],
                            "from": first, "to": last, "path": path, "duration": seconds, "voice_name": voice_name, "captions": captions})
            cursor = last / fps + line.get("gap", style["audio"]["gap"])
        requested = beat.get("duration", cursor - begin)
        if requested < cursor - begin - 1e-6:
            raise ValueError(f"{beat['id']}: durationが音声と間より短いです")
        cursor = frame(begin + requested, fps) / fps
        beats.append({"id": beat["id"], "from": frame(begin, fps), "to": frame(cursor, fps)})
    shots, audio = compile_edit(root, project, anchors, cursor, fps)
    warnings = []
    for sound in audio:
        if sound.get("volume", 1) == 0:
            continue
        analysis = run([find_executable("ffmpeg"), "-hide_banner", "-ss", str(sound.get("source_start", 0)),
                        "-t", str((sound["to"] - sound["from"]) / fps), "-i", root / sound["path"],
                        "-vn", "-af", "volumedetect", "-f", "null", "-"], capture=True)
        match = re.search(r"max_volume: ([-0-9.]+) dB", analysis.stderr)
        if match and float(match[1]) <= -90:
            warnings.append(f"選択した音素材の区間は無音です: {sound['path']} @ {sound.get('source_start', 0):.3f}s")
    result = {"title": project["title"], "video": video, "durationInFrames": frame(cursor, fps),
              "lines": records, "beats": beats, "shots": shots, "audio": audio,
              "subtitles": {**style["subtitles"], **project.get("subtitles", {})},
              "mix": style["audio"], "warnings": warnings, "speech": {"generated": generated, "reused": reused}}
    write_json(root / "work" / "timing.json", result)
    return result


def validate_output(root: Path, project: dict, timing: dict, output: Path, quality: str) -> dict:
    wanted = [(line["id"], line["text"]) for beat in project["beats"] for line in beat.get("lines", [])]
    if [(line["id"], line["text"]) for line in timing["lines"]] != wanted:
        raise ValueError("字幕・音声本文が台本と一致しません")
    for line in timing["lines"]:
        if line.get("captions") is not None and "".join(c["text"] for c in line["captions"]) != line["text"]:
            raise ValueError("字幕本文が音声原稿と一致しません")
    info = ffprobe(output)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not video or not audio:
        raise ValueError("完成動画の映像または音声がありません")
    if int(audio.get("sample_rate", 0)) != 48000:
        raise ValueError("完成動画の音声は48kHzである必要があります")
    fps = timing["video"]["fps"]
    expected = timing["durationInFrames"] / fps
    if abs(float(info["format"]["duration"]) - expected) > max(0.1, 2 / fps):
        raise ValueError("完成動画の尺が時間表と一致しません")
    scale = 0.5 if quality == "preview" else 1
    if (video["width"], video["height"]) != (int(timing["video"]["width"] * scale), int(timing["video"]["height"] * scale)):
        raise ValueError("完成動画の解像度が一致しません")
    from fractions import Fraction
    if abs(float(Fraction(video["avg_frame_rate"])) - fps) > 0.001:
        raise ValueError("完成動画が指定の固定FPSではありません")
    actual = [(line["id"], line["text"]) for line in timing["lines"]]
    wanted = [(line["id"], line["text"]) for beat in project["beats"] for line in beat.get("lines", [])]
    if actual != wanted:
        raise ValueError("音声本文が台本と一致しません")
    run([find_executable("ffmpeg"), "-v", "error", "-xerror", "-i", output, "-f", "null", "-"], capture=True)
    levels = measure_loudness(output)
    result = {"passed": True, "quality": quality, "file": output.relative_to(root).as_posix(),
              "duration": float(info["format"]["duration"]), "full_decode": "passed",
              "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "width": video["width"], "height": video["height"], "fps": fps,
              "sample_rate": int(audio["sample_rate"]), "loudness": {
                  key: float(levels[field]) if math.isfinite(float(levels[field])) else None
                  for key, field in [("integrated_lufs", "input_i"), ("true_peak_dbfs", "input_tp"), ("range_lu", "input_lra")]}}
    write_json(root / "output" / f"{quality}-validation.json", result)
    return result


def validate_thumbnail(root: Path) -> None:
    path = root / "output" / "thumbnail.jpg"
    if not path.is_file() or path.read_bytes()[:3] != b"\xff\xd8\xff":
        raise ValueError("output/thumbnail.jpgが必要です")
    info = ffprobe(path)["streams"][0]
    project = read_json(root / "project.json")
    video = {**read_json(REPO_ROOT / "style.json")["video"], **project.get("video", {})}
    portrait = video["height"] > video["width"]
    ratio = 9 / 16 if portrait else 16 / 9
    if info["height" if portrait else "width"] < 640 or abs(info["width"] / info["height"] - ratio) > 0.01:
        raise ValueError("サムネイルは動画と同じ画面比率で、横動画は幅640px以上、縦動画は高さ640px以上にしてください")


def measure_loudness(source: Path) -> dict:
    result = run([find_executable("ffmpeg"), "-hide_banner", "-i", source,
                  "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture=True)
    match = re.search(r'\{\s*"input_i"[\s\S]*?\}', result.stderr)
    if not match:
        raise ValueError("ラウドネスの測定に失敗しました")
    return json.loads(match.group())


def normalize_loudness(source: Path, output: Path, duration: float) -> None:
    """FFmpeg's measured two-pass EBU R128 normalization; picture packets are copied."""
    samples = round(number(duration, "duration", 0.001) * 48000)
    stats = measure_loudness(source)
    measured = ""
    if math.isfinite(float(stats["input_i"])):
        measured = (f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
                    f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
                    f":offset={stats['target_offset']}:linear=true")
    run([find_executable("ffmpeg"), "-v", "error", "-y", "-i", source,
         "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
         "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11{measured},aresample=48000,apad,atrim=end_sample={samples},asetpts=N/SR/TB",
         "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output], capture=True)

"""Versioned editorial decisions inside project.json; Remotion remains the renderer."""
from __future__ import annotations

import copy
import hashlib
import math
import re

from common import REPO_ROOT, read_json, project_file
from edit import compile_edit, frame, number, resolve_time, media_info

REGISTRY = read_json(REPO_ROOT / "editing/templates.v1.json")
EVENT_KEYS = {"id", "version", "effect", "pattern", "at", "duration", "intensity", "target", "params", "audio",
              "seed", "reason", "intent", "emotion", "importance", "variation", "media", "layers", "label", "direction"}


def bounded(value, label, minimum, maximum):
    result = number(value, label, minimum)
    if result > maximum:
        raise ValueError(f"{label}: {minimum}..{maximum}で指定してください")
    return result


def object_keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"{label}: 未対応のキーまたは不正なオブジェクトです")


def validate_matte(root, path):
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(project_file(root, path).read_bytes(), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.ndim != 3 or image.shape[2] != 4 or not 0 <= image[:, :, 3].min() < image[:, :, 3].max():
        raise ValueError('layersには実際に透過領域と被写体があるPNGが必要です')


def decisions(project):
    config = project.get("editing", {})
    object_keys(config, {"version", "events", "sounds", "policy", "caption_animation", "seed", "renderer"}, "editing")
    if config.get("version", 1) != 1 or isinstance(config.get("version", 1), bool):
        raise ValueError("editing.versionは1が必要です")
    if config.get("renderer", "cpu") not in {"cpu", "webgl"}:
        raise ValueError("editing.rendererはcpuまたはwebglです")
    if config.get("caption_animation", "none") not in {"none", "caption_pop"}:
        raise ValueError("caption_animationはnoneまたはcaption_popです")
    if not isinstance(config.get("events", []), list):
        raise ValueError("editing.eventsは配列です")
    if not isinstance(config.get('sounds', {}), dict):
        raise ValueError('editing.soundsは名前ごとのオブジェクトです')
    object_keys(config.get('policy', {}), set(REGISTRY['policy']), 'editing.policy')
    if 'seed' in config and not isinstance(config['seed'], str):
        raise ValueError('editing.seedは文字列です')
    ids, expanded = set(), []
    line_ids = {l["id"] for b in project["beats"] for l in b.get("lines", [])}
    shot_ids = {s.get("id", f"shot-{i + 1}") for i, s in enumerate(project["shots"])}
    for raw in config.get("events", []):
        object_keys(raw, EVENT_KEYS, "editing.event")
        eid = raw.get("id", "")
        if not isinstance(eid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", eid) or eid in ids:
            raise ValueError("演出idは一意の英数字・ハイフン・下線です")
        ids.add(eid)
        if raw.get("version", 1) != 1 or isinstance(raw.get("version", 1), bool):
            raise ValueError(f"{eid}: effect versionは1です")
        if bool(raw.get("effect")) == bool(raw.get("pattern")):
            raise ValueError(f"{eid}: effectとpatternのどちらか一つが必要です")
        if not isinstance(raw.get("reason"), str) or not raw["reason"].strip():
            raise ValueError(f"{eid}: 何を見せる演出かreasonを記してください")
        for key in ('seed', 'intent', 'emotion'):
            if key in raw and not isinstance(raw[key], str):
                raise ValueError(f'{eid}: {key}は文字列です')
        pattern = raw.get("pattern")
        if pattern and pattern not in REGISTRY["patterns"]:
            raise ValueError(f"未定義のpattern: {pattern}")
        target = raw.get("target", {})
        object_keys(target, {"shot", "line", "keyword", "anchor", "point"}, "target")
        for key, known in (("line", line_ids), ("shot", shot_ids)):
            if key in target and target[key] not in known:
                raise ValueError(f"{eid}: target.{key}が見つかりません")
        for key in ("anchor", "point"):
            if key in target:
                object_keys(target[key], {"x", "y"}, "target." + key)
                for axis in ("x", "y"):
                    bounded(target[key].get(axis), key + "." + axis, 0, 1)
        strength = bounded(raw.get("intensity", 0.5), "intensity", 0, 1)
        if "importance" in raw:
            bounded(raw["importance"], "importance", 0, 1)
        variation = bounded(raw.get("variation", 0), "variation", 0, 1)
        seed = str(raw.get("seed", f"{config.get('seed', project['title'])}:{eid}"))
        random_unit = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / 0xffffffff
        if pattern and "params" in raw:
            object_keys(raw['params'], set(REGISTRY['patterns'][pattern]), 'pattern.params')
            unknown = set(raw["params"]) - set(REGISTRY["patterns"][pattern])
            if unknown:
                raise ValueError(f"{eid}: pattern.paramsはeffect名ごとの設定です: {sorted(unknown)}")
        for index, name in enumerate(REGISTRY["patterns"][pattern] if pattern else [raw["effect"]]):
            if name not in REGISTRY["effects"]:
                raise ValueError(f"未定義のeffect: {name}")
            spec = REGISTRY["effects"][name]
            e = copy.deepcopy(raw)
            e.update(id=f"{eid}:{name}" if pattern else eid, group=eid, effect=name, version=1, seed=seed,
                     intensity=strength, target=target, stage=spec["stage"])
            values = raw.get("params", {}).get(name, {}) if pattern else raw.get("params", {})
            object_keys(values, set(spec["params"]), name + ".params")
            e["params"] = {key: bounded(values.get(key, limits[0]), f"{name}.{key}", limits[1], limits[2]) for key, limits in spec["params"].items()}
            if name == 'glitch_burst' and not e['params']['slices'].is_integer():
                raise ValueError('glitch_burst.slicesは整数です')
            lo, hi = spec["duration"][1:]
            duration = bounded(raw.get("duration", spec["duration"][0]) if not pattern else spec["duration"][0], name + ".duration", lo, hi)
            if pattern and "duration" in raw:
                raise ValueError(f"{eid}: 複合patternは各技法の時間を使用します。時間を変える場合は個別effectを指定してください")
            e["duration"] = max(lo, min(hi, duration * (1 + (random_unit * 2 - 1) * 0.08 * variation)))
            if strength == 0:
                continue
            if name in {"caption_pop", "keyword_highlight", "jump_cut_tighten"} and "line" not in target:
                raise ValueError(f"{eid}: target.lineが必要です")
            if spec["stage"] not in {"caption", "speech"} and "shot" not in target:
                raise ValueError(f"{eid}: target.shotが必要です")
            if name == "keyword_highlight":
                text = next(l["text"] for b in project["beats"] for l in b.get("lines", []) if l["id"] == target["line"])
                if not isinstance(target.get("keyword"), str) or not target["keyword"] or target["keyword"] not in text:
                    raise ValueError(f"{eid}: keywordは原稿内の文字列が必要です")
            if name == "callout" and (not isinstance(raw.get("label"), str) or not 1 <= len(raw["label"]) <= 20 or "point" not in target):
                raise ValueError(f"{eid}: calloutには20文字以内のlabelとtarget.pointが必要です")
            if name == "whip_transition" and raw.get("direction", "left") not in {"left", "right"}:
                raise ValueError("whip_transition.directionはleftまたはrightです")
            if name in {"rgb_split", "glitch_burst"} and config.get("renderer", "cpu") != "webgl":
                raise ValueError(f"{eid}: editing.renderer=webglを明示してください。GPU演出は省略しません")
            if index:
                e.pop("audio", None)  # One sound per editorial gesture, never per primitive.
            expanded.append(e)
    return expanded


def speech_edits(project):
    result = {}
    for e in decisions(project):
        if e["effect"] != "jump_cut_tighten":
            continue
        lid = e["target"]["line"]
        if lid in result:
            raise ValueError(f"{lid}: jump_cut_tightenの重複です")
        if "at" in e or "audio" in e:
            raise ValueError("jump_cut_tightenは発話全体が対象です。at/audioは使用できません")
        result[lid] = e
    return result


def event_time(value, lines, shots, duration, records=None):
    if isinstance(value, dict) and "word" in value:
        object_keys(value, {"line", "word", "edge", "offset"}, "at.word")
        record = next((r for r in records or [] if r["id"] == value.get("line")), None)
        word = value["word"]
        if not record or not record.get("captions"):
            raise ValueError("at.wordには文字時刻付き音声またはline.caption_pathが必要です。時刻を推測しません")
        if not isinstance(word, str) or not word or record["text"].count(word) != 1:
            raise ValueError("at.wordは原稿に一度だけ現れる文字列です")
        begin = record["text"].index(word)
        end, offset, found = begin + len(word), 0, {}
        for c in record["captions"]:
            if offset == begin:
                found["start"] = c["startMs"]
            offset += len(c["text"])
            if offset == end:
                found["end"] = c["endMs"]
        edge = value.get("edge", "start")
        if edge not in found:
            raise ValueError("at.wordの境界に一致する文字時刻がありません")
        return lines[record["id"]]["start"] + found[edge] / 1000 + number(value.get("offset", 0), "offset", -1e6)
    if isinstance(value, dict) and "shot" in value:
        object_keys(value, {"shot", "edge", "offset"}, "at")
        if value["shot"] not in shots or value.get("edge", "start") not in {"start", "end"}:
            raise ValueError("不正なショット参照")
        shot = shots[value["shot"]]
        return shot[value.get("edge", "start")] + number(value.get("offset", 0), "offset", -1e6)
    return resolve_time(value, lines, duration)


def sync_frame(event, fps, sync=None):
    kind = sync or REGISTRY["effects"][event["effect"]]["sync"]
    length = event["to"] - event["from"]
    if kind == "start":
        offset = 0
    elif kind == "end":
        offset = length - 1
    elif kind == "peak_velocity":
        offset = length // 2 if event["effect"] in {"whip_transition", "speed_ramp"} else 1
    elif kind == "impact":
        offset = max(1, round((length - 1) * 0.4)) if event["effect"] == "punch_zoom" else 0
    elif kind == "landing":
        if event['stage'] == 'layers':
            offset = max(1, min(round(fps * .3), math.floor((length - 1) * .6)))
        else:
            offset = min(length - 1, round(fps * 0.25)) if event["effect"] == "callout" else length - 1
    else:
        raise ValueError(f"不正なSE同期点: {kind}")
    return event["from"] + offset


def compile_effects(root, project, records, shots, duration, fps):
    config = project.get("editing", {})
    lines = {l["id"]: {"start": l["from"] / fps, "end": l["to"] / fps} for l in records}
    shot_times = {s["id"]: {"start": s["from"] / fps, "end": s["to"] / fps} for s in shots}
    by_shot = {s["id"]: s for s in shots}
    compiled, sounds, warnings = [], [], []
    for e in decisions(project):
        if e["stage"] == "speech":
            e.update(from_=0)
            e["from"], e["to"] = [frame(lines[e["target"]["line"]][edge], fps) for edge in ("start", "end")]
            e.pop("from_", None)
        else:
            fallback = {"line": e["target"]["line"]} if "line" in e["target"] else {"shot": e["target"]["shot"]}
            start = frame(event_time(e.get("at", fallback), lines, shot_times, duration, records), fps)
            length = max(2, frame(e["duration"], fps))
            e["from"], e["to"] = start, start + length
            if e["effect"] == "whip_transition":
                shot = by_shot[e["target"]["shot"]]
                index = shots.index(shot)
                if not index or start != shot["from"]:
                    raise ValueError("whip_transition.atは次ショットの開始点です")
                e["from"], e["to"] = start - length // 2, start + length - length // 2
                e["previous_shot"] = shots[index - 1]["id"]
                for s in (shots[index - 1], shot):
                    if s["media"] != "video":
                        raise ValueError("whip_transitionは動画ショット間に指定してください")
                    available = float(media_info(root, s["path"], {})["format"]["duration"])
                    first = s["source_start"] + (e["from"] - s["from"]) / fps * s["speed"]
                    last = s["source_start"] + (e["to"] - s["from"]) / fps * s["speed"]
                    if first < 0 or last > available:
                        raise ValueError("whip_transition: 前後の動画素材の余白が足りません")
        if e["from"] < 0 or e["to"] > frame(duration, fps):
            raise ValueError(f"{e['id']}: 演出区間が動画の範囲外です")
        shot = by_shot.get(e["target"].get("shot"))
        if shot and e["effect"] != "whip_transition" and not (shot["from"] <= e["from"] < e["to"] <= shot["to"]):
            raise ValueError(f"{e['id']}: 演出が対象ショットをまたいでいます")
        if e["effect"] in {"freeze_frame", "speed_ramp"} and shot["media"] != "video":
            raise ValueError(f"{e['id']}: 動画が必要です")
        if e["stage"] == "caption":
            line = lines[e["target"]["line"]]
            if e["from"] < frame(line["start"], fps) or e["to"] > frame(line["end"], fps):
                raise ValueError(f"{e['id']}: 字幕の演出は発話区間内にしてください")
        if e["effect"] == "broll_cutaway":
            if not isinstance(e.get("media"), dict) or "path" not in e["media"]:
                raise ValueError("broll_cutaway.mediaに実際の素材指定が必要です")
            media = {**e["media"], "id": e["id"], "from": 0, "to": e["duration"]}
            cutaway, _ = compile_edit(root, {"shots": [media]}, {}, e["duration"], fps)
            e["media"] = {**cutaway[0], "from": e["from"], "to": e["to"]}
        if e["stage"] == "layers":
            e['attack_frames'] = sync_frame(e, fps, 'landing') - e['from']
            e['release_frames'] = max(1, min(round(fps * .2), e['to'] - e['from'] - 1 - e['attack_frames']))
            if not isinstance(e.get("layers"), list) or not e["layers"]:
                raise ValueError(f"{e['id']}: 位置合わせ済みの透過layersが必要です。自動切り抜きはしません")
            for layer in e["layers"]:
                object_keys(layer, {"path", "depth"}, "layer")
                bounded(layer.get("depth", 1), "layer.depth", 0.1, 2)
                info = media_info(root, layer.get("path"), {})
                stream = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
                if (stream.get("width"), stream.get("height")) != (shot["source_width"], shot["source_height"]):
                    raise ValueError("layersは対象ショットと同じピクセル寸法で位置合わせしてください")
                alpha = stream.get('pix_fmt', '').startswith(('rgba', 'bgra', 'argb', 'abgr', 'gbrap', 'yuva', 'ya8', 'ya16'))
                if not layer["path"].lower().endswith(".png") or not alpha:
                    raise ValueError("v1のlayersは透過PNGです。動画マッティングは評価段階です")
                validate_matte(root, layer['path'])
            if shot["media"] != "image":
                raise ValueError("v1のparallax/subject_popoutは静止画と透過PNGの組です")
        e["sync_frame"] = sync_frame(e, fps)
        if e.get("audio"):
            cue = e["audio"]
            object_keys(cue, {"sfx", "sync", "offset_ms", "volume"}, "event.audio")
            bank = config.get("sounds", {})
            if cue.get("sfx") not in bank:
                raise ValueError(f"{e['id']}: 未定義のsfx")
            sound = bank[cue["sfx"]]
            object_keys(sound, {"path", "marker", "duration", "volume", "source_start"}, "editing.sounds")
            info = media_info(root, sound.get("path"), {})
            if not any(s["codec_type"] == "audio" for s in info["streams"]):
                raise ValueError("sfxに音声がありません")
            total = float(info["format"]["duration"])
            source_start = bounded(sound.get("source_start", 0), "sfx.source_start", 0, total)
            length = bounded(sound.get("duration", total - source_start), "sfx.duration", 1 / fps, total - source_start)
            marker = bounded(sound.get("marker", 0), "sfx.marker", 0, length)
            sync = sync_frame(e, fps, cue.get("sync"))
            begin = sync - frame(marker, fps) + frame(bounded(cue.get("offset_ms", 0), "offset_ms", -1000, 1000) / 1000, fps)
            end = begin + frame(length, fps)
            if begin < 0 or end > frame(duration, fps):
                raise ValueError(f"{e['id']}: SEが動画の範囲外です。音源区間・markerを調整してください")
            sounds.append({"path": sound["path"], "from": begin, "to": end, "source_start": source_start,
                           "source_duration": length, "marker": marker,
                           "volume": bounded(cue.get("volume", sound.get("volume", 0.3)), "sfx.volume", 0, 2),
                           "fade_in": 0, "fade_out": 0, "role": f"sfx:{e['group']}", "sync_frame": sync})
        compiled.append(e)
    for e in compiled:
        if e["effect"] != "whip_transition":
            continue
        participants = {e["target"]["shot"], e["previous_shot"]}
        if any(a["target"].get("shot") in participants and a["effect"] in {"speed_ramp", "freeze_frame"} for a in compiled):
            raise ValueError("v1ではwhipの前後ショットと時間加工を併用できません")
    # These are compatibility checks, not subjective quality scores.
    for i, a in enumerate(compiled):
        for b in compiled[i + 1:]:
            if a["target"].get("shot") != b["target"].get("shot"):
                continue
            same = a["effect"] == b["effect"]
            overlap = a["from"] < b["to"] and b["from"] < a["to"]
            pair = {a["effect"], b["effect"]}
            if a['stage'] == b['stage'] == 'layers':
                raise ValueError("v1の透過レイヤー演出は1ショット1件です")
            if (same and overlap) or (pair == {"speed_ramp", "freeze_frame"}):
                raise ValueError(f"同じ対象で競合する演出: {a['id']} / {b['id']}")
            if "whip_transition" in pair and pair & {"speed_ramp", "freeze_frame"}:
                raise ValueError("v1ではwhipの対象ショットと時間加工を併用できません")
    policy = {**REGISTRY["policy"], **config.get("policy", {})}
    object_keys(policy, {"strong_effect_cooldown", "max_per_10s", "never_stack"}, "editing.policy")
    cooldown = bounded(policy["strong_effect_cooldown"], "strong_effect_cooldown", 0, 30)
    strong = {"punch_zoom", "impact_shake", "flash_cut", "whip_transition", "rgb_split", "glitch_burst"}
    gestures = {}
    for e in compiled:
        if e["effect"] in strong and e["intensity"] >= 0.5:
            gestures.setdefault(e["group"], e)
    ordered = sorted(gestures.values(), key=lambda e: e["from"])
    for a, b in zip(ordered, ordered[1:]):
        if (b["from"] - a["from"]) / fps < cooldown:
            warnings.append(f"強い演出が近接: {a['group']} / {b['group']}。意図と完成映像を確認")
    for name, limit in policy["max_per_10s"].items():
        if name not in REGISTRY["effects"]:
            raise ValueError("max_per_10sに未定義effect")
        bounded(limit, "max_per_10s", 0, 100)
        entries = [e for e in compiled if e["effect"] == name]
        if any(sum(a["from"] <= b["from"] < a["from"] + fps * 10 for b in entries) > limit for a in entries):
            warnings.append(f"{name}: 10秒区間の参考上限{limit}回を超過。採用判断は編集者が行う")
    for pair in policy["never_stack"]:
        if not isinstance(pair, list) or len(pair) < 2 or any(p not in REGISTRY["effects"] for p in pair):
            raise ValueError("never_stackは既知effect名の組です")
        for e in compiled:
            active = {a["effect"] for a in compiled if a["from"] <= e["from"] < a["to"]}
            if set(pair) <= active:
                warnings.append(f"重ね合わせを確認: {' + '.join(pair)} @ {e['from'] / fps:.2f}s")
                break
    return compiled, sounds, warnings


def subtitle_config(style, project):
    config = {**style['subtitles'], **project.get('subtitles', {})}
    for key in ('font_size', 'font_weight', 'line_height', 'min_height', 'max_chars_per_line', 'max_lines'):
        number(config[key], 'subtitles.' + key, 0.001)
    for key in ('max_chars_per_line', 'max_lines'):
        if int(config[key]) != config[key]:
            raise ValueError('字幕の文字数・行数は整数です')
    for key in ('bottom', 'side_margin', 'inner_outline_width', 'outer_outline_width'):
        number(config[key], 'subtitles.' + key)
    safe = config.get('safe_area', {'left': 80, 'right': 140, 'top': 100, 'bottom': 300})
    object_keys(safe, {'left', 'right', 'top', 'bottom'}, 'subtitles.safe_area')
    for key in ('left', 'right', 'top', 'bottom'):
        number(safe.get(key), 'safe_area.' + key)
    if safe['left'] + safe['right'] >= 1080 or safe['top'] + safe['bottom'] >= 1920 or config['side_margin'] >= 540:
        raise ValueError('字幕の表示可能領域がありません')
    config['safe_area'] = safe
    return config

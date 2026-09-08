"""Reproduce the real-footage A/B comparison; no upload, no packaged media or TTS cache."""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import shutil
import sys
import subprocess
import hashlib

from create_demo import ROOT, main as download_nasa
sys.path.insert(0, str(ROOT / "tools"))
from common import read_json, write_json, project_file


def link_or_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def project():
    p = read_json(ROOT / "examples/aivisspeech.project.json")
    p["title"] = "ロケットを守る水｜編集文法v1"
    p.pop("youtube", None)
    script = [
        ("h1", "発射台に、滝のような水。", 0.28),
        ("q1", "これ、何のためだと思う？", 0.22),
        ("h2", "実は、ロケットを音から守っている。", 0.18),
        ("c1", "発射の音は、機体を傷めるほど強烈だ。", 0.18),
        ("c2", "大切な荷物にも、負担がかかる。", 0.24),
        ("a1", "そこで水を流し、音のエネルギーを弱める。", 0.18),
        ("p1", "映っているのは、発射台の放水試験。", 0.2),
        ("p2", "本番に備え、水の流れを確かめている。", 0.2),
        ("end", "この水も、打ち上げを支える仕組みなんだ。", 0.7),
    ]
    p["beats"] = [{"id": "story", "lines": [{"id": key, "text": text, "gap": gap} for key, text, gap in script]}]
    selections = [
        ("opening", "water.mp4", 58.8, None, "q1", 0.46, 0.5, "落ちる水の勢いで疑問を作る。元映像内の次のカットの前で切る"),
        ("question", "water.mp4", 66, "q1", "h2", 0.46, 0.5, "問いに合わせて放水の側面へ切り替える"),
        ("answer", "drone.mp4", 13, "h2", "c1", 0.24, 0.5, "音を抑える仕組みの説明に放水口を見せる"),
        ("ignition", "launch.mp4", 49, "c1", "c2", 0.5, 0.5, "音源となる点火と上昇を見せる"),
        ("climb", "launch.mp4", 54, "c2", "a1", 0.5, 0.5, "機体への負担の説明を上昇する機体につなぐ"),
        ("flow", "water.mp4", 76, "a1", "p1", 0.5, 0.63, "発射台を覆う水を見せる"),
        ("test", "drone.mp4", 17, "p1", "p2", 0.24, 0.5, "短い停止で試験設備の配置に目を止める"),
        ("confirm", "water.mp4", 66, "p2", "end", 0.46, 0.5, "試験の流れを再び動きとして見せる"),
        ("payoff", "water.mp4", 58.1, "end", None, 0.46, 0.5, "冒頭と同じ水の姿を、意味が分かった状態で回収する"),
    ]
    p["shots"] = [{"id": sid, "path": "assets/" + name, "source_start": source,
                    "from": {"line": start} if start else 0, "to": {"line": end} if end else None,
                    "camera": [{"at": 0, "x": x, "y": y, "zoom": 1}], "reason": reason}
                   for sid, name, source, start, end, x, y, reason in selections]
    p["audio"] = [
        {"path": "assets/water.mp4", "source_start": 58.8, "to": {"line": "c1"}, "volume": 0.45, "duck": True, "fade_in": 0.08, "fade_out": 0.25},
        {"path": "assets/launch-sound.wav", "from": {"line": "c1", "offset": -0.35}, "to": {"line": "a1", "offset": 0.1}, "volume": 0.25, "duck": True, "fade_in": 0.15, "fade_out": 0.3},
        {"path": "assets/water.mp4", "source_start": 58.8, "from": {"line": "a1", "offset": -0.2}, "volume": 0.4, "duck": True, "fade_in": 0.2, "fade_out": 0.3},
    ]
    p["editing"] = {"version": 1, "seed": "water-editorial-v1", "caption_animation": "caption_pop", "sounds": {
        "soft_hit": {"path": "assets/switch.wav", "marker": 0.121406, "volume": 0.22},
        "click": {"path": "assets/mouse-click.wav", "source_start": 0.10, "duration": 0.09, "marker": 0.023016, "volume": 0.15},
    }, "events": [
        {"id": "tight-hook", "effect": "jump_cut_tighten", "target": {"line": "h1"}, "reason": "冒頭の発話前後の無音と次の問いまでの間を整理"},
        {"id": "sound-reveal", "pattern": "emphasize_claim", "at": {"line": "h2", "offset": 1.8}, "intensity": 0.52,
         "target": {"shot": "answer", "line": "h2", "keyword": "音", "anchor": {"x": 0.48, "y": 0.5}}, "audio": {"sfx": "soft_hit", "sync": "impact"}, "reason": "予想外の答えである音に、寄りと強調語と短い音を合わせる"},
        {"id": "ignition-hit", "effect": "impact_shake", "at": {"line": "c1", "offset": 0.3}, "intensity": 0.28, "target": {"shot": "ignition"}, "reason": "点火の衝撃を短い減衰で補う"},
        {"id": "ignition-flash", "effect": "flash_cut", "at": {"line": "c1"}, "intensity": 0.18, "target": {"shot": "ignition"}, "reason": "点火カットにごく短い光のアクセント"},
        {"id": "water-evidence", "effect": "broll_cutaway", "at": {"line": "a1", "offset": 0.3}, "duration": 1.8, "target": {"shot": "flow"},
         "media": {"path": "assets/water.mp4", "source_start": 59.6, "camera": [{"at": 0, "x": 0.46, "y": 0.5, "zoom": 1}]}, "reason": "音を弱める説明に、実際に落ちる大量の水を挿入"},
        {"id": "inspect-test", "effect": "freeze_frame", "at": {"line": "p1", "offset": 2.35}, "duration": 0.55, "target": {"shot": "test"},
         "audio": {"sfx": "click", "sync": "start"}, "reason": "放水試験であることを確かめる瞬間だけ画を止める。素材不足の補完ではない"},
        {"id": "test-word", "effect": "keyword_highlight", "at": {"line": "p1", "offset": 2.35}, "duration": 0.55, "intensity": 0.35,
         "target": {"line": "p1", "keyword": "放水試験"}, "reason": "打ち上げ映像と試験映像の区別を原稿の言葉で示す"},
    ]}
    for sound, key in zip(p['audio'], ('water-opening', 'launch-field', 'water-payoff')):
        sound['id'] = key
    p['sound_design'] = {'version': 1, 'beats': [{
        'beat': 'story',
        'ambience': {'decision': 'use', 'reason': 'openingから放水音、ignitionから発射音、flowから放水音でつなぐ',
                     'refs': ['audio:water-opening', 'audio:launch-field', 'audio:water-payoff']},
        'sfx': {'decision': 'use', 'reason': 'answerの発見とtestの停止だけを短く強調する',
                'refs': ['event:sound-reveal', 'event:inspect-test']},
        'music': {'decision': 'omit', 'reason': '水と発射の現場音を優先する', 'refs': []},
        'silence': {'decision': 'omit', 'reason': '現場音をカット越しに連続させる', 'refs': []},
    }]}
    return p


def align_baseline(root, baseline):
    """Keep the A/B narration byte-identical before the deliberate silence trim."""
    edited = read_json(root / 'project.json')
    clean = read_json(baseline / 'project.json')
    timing = read_json(root / 'work/timing.json')
    wanted = [(l['id'], l['text']) for b in edited['beats'] for l in b.get('lines', [])]
    lines = [l for b in clean['beats'] for l in b.get('lines', [])]
    if wanted != [(l['id'], l['text']) for l in lines] or wanted != [(l['id'], l['text']) for l in timing['lines']]:
        raise ValueError('同じ原稿のA/B案件と、現在のprepare結果が必要です')
    for line, record in zip(lines, timing['lines']):
        if record.get('captions'):
            raise ValueError('このサンプルの音声共有はAivisSpeechの文字時刻なし音声を対象とします')
        source = project_file(root, record['trim']['source'] if record.get('trim') else record['path'])
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        relative = f'assets/narration/{line["id"]}-{digest[:16]}{source.suffix}'
        link_or_copy(source, baseline / relative)
        if hashlib.sha256((baseline / relative).read_bytes()).hexdigest() != digest:
            raise ValueError('共有音声の読み戻しが一致しません')
        line.update(path=relative, credit=record['voice_name'])
    write_json(baseline / 'project.json', clean)
    print('Baseline now uses the same original narration bytes; build the baseline again.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", nargs="?", type=Path, default=ROOT / "projects/editing-grammar-v1")
    parser.add_argument("--source-project", type=Path, help="同じNASA原本を持つ既存案件。素材だけをハードリンク")
    parser.add_argument('--align-baseline', action='store_true', help='prepare済み案件の原音声をA/B共通にする。既存baselineのline.pathだけ更新')
    args = parser.parse_args()
    root = args.destination.resolve()
    baseline = root.with_name(root.name + "-baseline")
    if args.align_baseline:
        align_baseline(root, baseline)
        return
    if (root / "project.json").exists() or (baseline / "project.json").exists():
        raise SystemExit("既存の編集指定を上書きしません。別の出力先を指定してください")
    if args.source_project:
        for name in ("water.mp4", "drone.mp4", "launch.mp4", "launch-sound.wav"):
            link_or_copy(args.source_project.resolve() / "assets" / name, root / "assets" / name)
    else:
        sys.argv = [sys.argv[0], str(root)]
        download_nasa()
    for name in ("switch.wav", "mouse-click.wav"):
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--max-time", "30",
                        "https://remotion.media/" + name, "--output", str(root / "assets" / name)], check=True)
    p = project()
    write_json(root / "project.json", p)
    clean = copy.deepcopy(p)
    clean["title"] = "ロケットを守る水｜演出なし比較"
    clean.pop("editing")
    clean['sound_design']['beats'][0]['sfx'] = {'decision': 'omit', 'reason': 'SEなしの比較版', 'refs': []}
    clean["subtitles"] = {"font_size": 68, "max_chars_per_line": 11}
    for source in (root / "assets").iterdir():
        link_or_copy(source, baseline / "assets" / source.name)
    write_json(baseline / "project.json", clean)
    print(root)
    print(baseline)


if __name__ == "__main__":
    main()

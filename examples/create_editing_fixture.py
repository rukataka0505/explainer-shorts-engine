"""Synthetic engineering fixture for all 16 primitives (not documentary footage)."""
from __future__ import annotations

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from common import find_executable, read_json, run, write_json


def create(root: Path, gpu=True):
    if (root / 'project.json').exists() and read_json(root / 'project.json').get('title') != 'Editing regression v1':
        raise ValueError('既存の制作案件を検証用素材で上書きできません')
    assets = root / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_executable('ffmpeg')
    for filename, source in [('motion.mp4', 'testsrc2=s=360x640:r=30:d=12'),
                              ('cutaway.mp4', 'color=c=0x145B31:s=360x640:r=30:d=5')]:
        run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', source, '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', assets / filename], capture=True)
    run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
         '-af', "volume='if(between(t,0.35,1.65),0.1,0)':eval=frame", assets / 'tone.wav'], capture=True)
    run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=1800:sample_rate=48000:duration=0.12',
         '-af', 'afade=t=out:st=0.03:d=0.09', assets / 'cue.wav'], capture=True)
    for filename, color in [('plate.png', '0x182F43'), ('foreground.png', 'black@0')]:
        # Negotiate RGBA inside lavfi; converting an opaque YUV source later loses alpha.
        source = f'color=c={color}:s=360x640:r=1,format=rgba'
        if filename == 'foreground.png':
            source += ',drawbox=x=120:y=160:w=120:h=200:c=0xD2B584:t=fill:replace=1'
        run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', source, '-frames:v', '1', assets / filename], capture=True)
    names = ['jump_cut_tighten', 'caption_pop', 'keyword_highlight', 'punch_zoom', 'impact_shake', 'flash_cut',
             'freeze_frame', 'broll_cutaway', 'whip_transition', 'focus_reveal', 'callout', 'parallax_push', 'subject_popout', 'speed_ramp']
    if gpu:
        names += ['rgb_split', 'glitch_burst']
    beats, shots, events = [], [], []
    for i, name in enumerate(names):
        begin, end = i * 2.2, (i + 1) * 2.2
        line_id, shot_id = f'line{i}', f'shot{i}'
        beats.append({'id': f'beat{i}', 'duration': 2.2, 'lines': [{'id': line_id, 'text': '編集の動作を検証。', 'path': 'assets/tone.wav', 'gap': 0.2}]})
        layered = name in {'parallax_push', 'subject_popout'}
        shots.append({'id': shot_id, 'path': 'assets/plate.png' if layered else 'assets/motion.mp4', 'source_start': 0 if layered else 2,
                      'from': begin, 'to': end, 'reason': f'{name}: 合成したテスト素材で動作を検査'})
        e = {'id': name, 'effect': name, 'at': begin + .4, 'target': {'shot': shot_id, 'line': line_id, 'keyword': '編集'}, 'reason': f'{name}の独立した回帰検査'}
        if name == 'jump_cut_tighten':
            e.pop('at')
        if name == 'caption_pop':
            e['audio'] = {'sfx': 'cue', 'sync': 'landing'}
        if name == 'whip_transition':
            e['at'] = {'shot': shot_id}
        if name == 'broll_cutaway':
            e['media'] = {'path': 'assets/cutaway.mp4'}
            e['duration'] = 1.2
        if name == 'callout':
            e['label'] = '注目'
            e['target']['point'] = {'x': .5, 'y': .35}
        if layered:
            e['layers'] = [{'path': 'assets/foreground.png', 'depth': 1.5}]
        events.append(e)
    p = {'title': 'Editing regression v1', 'video': {'width': 360, 'height': 640, 'fps': 30}, 'beats': beats, 'shots': shots,
         'editing': {'version': 1, 'renderer': 'webgl' if gpu else 'cpu', 'events': events, 'sounds': {'cue': {'path': 'assets/cue.wav', 'volume': .35}}},
         'research': [{'supports': '合成パターン・矩形・テスト音のみ。実写や人手編集の品質比較ではない。'}]}
    write_json(root / 'project.json', p)
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', type=Path, default=ROOT / 'projects/editing-fixture-v1')
    parser.add_argument('--cpu', action='store_true', help='GPUの2演出を除いた14演出で作成')
    args = parser.parse_args()
    destination = args.destination.resolve()
    create(destination, not args.cpu)
    print(destination)

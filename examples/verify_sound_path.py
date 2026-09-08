"""Read-only waveform audit of the two editing-grammar-v1 SE windows.

No render or TTS. Fits overlapping original tracks so narration cannot be
mistaken for evidence of SE. Constant gain per short window is an approximation;
correlation is technical evidence, not a listening/creative-quality pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import find_executable, read_json, write_json
from production import timing_digest


def audit(root):
    timing = read_json(root / 'work/timing.json')
    receipt = read_json(root / 'output/final-validation.json')
    output = root / receipt['file']
    checks = {
        'project': hashlib.sha256((root / 'project.json').read_bytes()).hexdigest() == receipt['project_sha256'],
        'timing': timing_digest(timing) == receipt['timing_sha256'],
        'output': hashlib.sha256(output.read_bytes()).hexdigest() == receipt['sha256'],
    }
    if not all(checks.values()):
        raise ValueError(f'検証対象がレンダー時と不一致です: {checks}')
    cache = {}
    def pcm(path):
        if path not in cache:
            data = subprocess.check_output([str(find_executable('ffmpeg')), '-v', 'error', '-i', str(path),
                                            '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
            cache[path] = np.frombuffer(data, dtype='<f4').astype(float)
        return cache[path]
    fps = timing['video']['fps']
    rows = []
    for cue in timing['audio']:
        if not cue.get('role', '').startswith('sfx:'):
            continue
        start = round(cue['from'] / fps * 48000)
        n = min(len(pcm(root / cue['path'])), round((cue['to'] - cue['from']) / fps * 48000))
        columns, names = [], []
        for track in timing['lines'] + timing['audio']:
            if track['to'] <= cue['from'] or track['from'] >= cue['to']:
                continue
            source = pcm(root / track['path'])
            pos = start - round(track['from'] / fps * 48000) + round(round(track.get('source_start', 0) * fps) / fps * 48000)
            samples = np.zeros(n)
            lo, hi = max(0, -pos), min(n, len(source) - pos, round(track['to'] / fps * 48000) - start)
            if hi > lo:
                samples[lo:hi] = source[pos + lo:pos + hi]
            columns.append(samples)
            names.append(track.get('role', track.get('id', track['path'])))
        matrix = np.stack(columns, axis=1)
        index = names.index(cue['role'])
        x = columns[index]
        row = {'cue': cue['role'], 'sync_seconds': cue['sync_frame'] / fps,
               'source_peak_dbfs': float(20 * np.log10(max(np.max(np.abs(x)), 1e-12))),
               'expected_pcm_gain': cue['volume'] * 10 ** (timing['mix'].get('headroom_db', -6) / 20), 'stages': {}}
        for stage, path in [('pcm', root / 'work/final-rendered.wav'), ('aac', output)]:
            y = pcm(path)[start:start+n]
            gains = np.linalg.lstsq(matrix, y, rcond=None)[0]
            separated = y - np.delete(matrix, index, axis=1) @ np.delete(gains, index)
            correlation = float(np.corrcoef(x, separated)[0, 1])
            row['stages'][stage] = {'source_correlation': correlation, 'fitted_gain': float(gains[index])}
            if correlation < .85 or gains[index] <= 0:
                raise ValueError(f'{cue["role"]}/{stage}: SEの存在を十分に確認できません')
        rows.append(row)
    if not rows:
        raise ValueError('検査対象のSEがありません')
    report = {'artifact_checks': checks, 'cues': rows, 'loudness': receipt['loudness'],
              'method': '短いSE区間で同時再生する原音源を最小二乗分離。既存サンプル用の近似検証。',
              'auditory_review': '未実施。聞こえ方・意味・強勢への同期は別途試聴で判断。'}
    write_json(root / 'work/audio-path-audit.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?', type=Path, default=Path('projects/editing-grammar-v1'))
    print(json.dumps(audit(parser.parse_args().project.resolve()), ensure_ascii=False))

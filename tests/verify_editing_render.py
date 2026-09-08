"""Inspect real rendered pixels/audio, then compare compact visual reference samples.

Run after rendering examples/create_editing_fixture.py with --quality final.
--update-reference is an explicit, reviewable baseline update, never an automatic retry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from common import find_executable, read_json, write_json


def read_frame(path, frame):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, image = cap.read()
        if not ok:
            raise AssertionError(f'Cannot decode {path} frame {frame}')
        return image
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', nargs='?', type=Path, default=ROOT / 'projects/editing-fixture-v1')
    parser.add_argument('--update-reference', action='store_true')
    args = parser.parse_args()
    root = args.project.resolve()
    timing = read_json(root / 'work/timing.json')
    receipt = read_json(root / 'output/final-validation.json')
    import hashlib
    movie = root / receipt['file']
    assert receipt['passed'] and hashlib.sha256(movie.read_bytes()).hexdigest() == receipt['sha256']
    assert receipt['project_sha256'] == hashlib.sha256((root / 'project.json').read_bytes()).hexdigest()
    events = {e['effect']: e for e in timing['editing']['events']}
    assert len(events) == 16, 'All 16 primitives must be rendered'
    assert receipt['width'] == 360 and receipt['height'] == 640 and receipt['fps'] == 30
    frames = {}
    def picture(f):
        if f not in frames:
            frames[f] = read_frame(movie, f)
        return frames[f]
    # Ignore captions for media-time comparisons.
    roi = lambda im: im[50:370, 30:330].astype(float)
    difference = lambda a, b: float(np.abs(roi(a) - roi(b)).mean())
    freeze = events['freeze_frame']
    freeze_diff = difference(picture(freeze['from'] + 2), picture(freeze['to'] - 2))
    assert freeze_diff < 1.2, f'Freeze did not hold the selected pixels: {freeze_diff}'
    assert difference(picture(freeze['to'] + 5), picture(freeze['to'] - 2)) > 2, 'Freeze never resumed'
    cutaway = events['broll_cutaway']
    green = picture(cutaway['from'] + 3)[180, 180]
    assert green[1] > green[0] * 1.5 and green[1] > green[2] * 1.5, f'Cutaway is absent: {green}'
    flash = events['flash_cut']
    assert float(picture(flash['from'])[60:360].mean()) > float(picture(flash['to'] + 1)[60:360].mean()) + 50, 'Flash is absent'
    # The speed ramp must reach the right source moment, not freeze/pad its final frames.
    speed = events['speed_ramp']
    shot = next(s for s in timing['shots'] if s['id'] == speed['target']['shot'])
    temporal = read_json((root / shot['path']).with_suffix('.json'))
    assert temporal['consumed_seconds'] > (shot['to'] - shot['from']) / 30 + .2
    original = root / shot['original_path']
    # Canvas video decoding and final BT.709 encoding can change the RGB values.
    # Identify the moving source frame from edges, including the curve midpoint.
    # A broad search must select the expected moment within one source frame.
    ramp_matches = []
    for global_frame in (speed['sync_frame'], speed['to'] - 1, shot['to'] - 1):
        local_seconds = (global_frame - shot['from']) / 30
        segment = next(s for s in reversed(temporal['segments']) if s['output_from'] <= local_seconds)
        source_seconds = segment['source_from'] + (local_seconds - segment['output_from']) * segment['speed']
        expected = round((shot['original_source_start'] + source_seconds) * 30)
        edges = lambda im: cv2.Canny(im[:370, 10:350], 60, 130)
        actual = edges(picture(global_frame))
        matches = [(f, float(cv2.matchTemplate(actual, edges(read_frame(original, f)), cv2.TM_CCOEFF_NORMED)[0, 0]))
                   for f in range(expected - 8, expected + 9)]
        matched, correlation = max(matches, key=lambda pair: pair[1])
        assert abs(matched - expected) <= 1 and correlation > .5, f'Wrong ramp source frame: {expected=}, {matched=}, {correlation=}'
        ramp_matches.append({'output_frame': global_frame, 'expected_source_frame': expected, 'matched_source_frame': matched, 'edge_correlation': correlation})
    # Foreground remains present before/after the gesture; it must not pop out of existence.
    for name in ('parallax_push', 'subject_popout'):
        e = events[name]
        for f in (e['from'] - 2, e['to'] + 2):
            bgr = picture(f)[240, 180]
            assert bgr[2] > bgr[0] + 20, f'{name}: foreground disappeared outside the gesture'
    # Verify leading/trailing silence was removed and internal tone stayed audible.
    line = timing['lines'][0]
    assert line['trim']['trim_start'] > .2 and line['trim']['trim_end'] > .2
    p = subprocess.run([str(find_executable('ffmpeg')), '-v', 'error', '-i', str(root / line['path']), '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], check=True, capture_output=True)
    samples = np.frombuffer(p.stdout, dtype='<f4')
    assert np.sqrt(np.mean(samples ** 2)) > .005, 'Tightening removed the speech signal'
    assert -17 < receipt['loudness']['integrated_lufs'] < -15
    assert receipt['loudness']['true_peak_dbfs'] < -.5
    assert receipt['raw_mix_loudness']['true_peak_dbfs'] < -.5
    # A unique 1800Hz cue must retain its attack at the caption's visual landing.
    cue = next(s for s in timing['audio'] if s.get('role') == 'sfx:caption_pop')
    p = subprocess.run([str(find_executable('ffmpeg')), '-v', 'error', '-i', str(movie), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], check=True, capture_output=True)
    mixed = np.frombuffer(p.stdout, dtype='<f4')
    def cue_level(second):
        samples = mixed[round(second * 48000):round(second * 48000) + 960]
        return float(abs(np.sum(samples * np.exp(-2j * np.pi * 1800 * np.arange(960) / 48000))) * 2 / 960)
    landing = events['caption_pop']['sync_frame'] / 30
    attack = cue_level(landing + .004)
    before = cue_level(landing - .08)
    after = cue_level(cue['to'] / 30 + .06)
    assert attack > .005 and attack > max(before, after) * 8, 'The SFX attack is missing or displaced from the visual landing'
    signatures = {}
    sheet = []
    for name, e in events.items():
        points = sorted({e['from'], e['sync_frame'], e['to'] - 1})
        for f in points:
            image = picture(f)
            signatures[f'{name}:{f - e["from"]}'] = cv2.resize(image, (9, 16), interpolation=cv2.INTER_AREA).reshape(-1).tolist()
        thumb = cv2.resize(picture(e['sync_frame']), (180, 320))
        labelled = np.full((346, 180, 3), 24, np.uint8)
        labelled[:320] = thumb
        cv2.putText(labelled, name, (5, 337), cv2.FONT_HERSHEY_SIMPLEX, .36, (255, 255, 255), 1)
        sheet.append(labelled)
    contact = np.vstack([np.hstack(sheet[i:i + 4]) for i in range(0, len(sheet), 4)])
    ok, encoded = cv2.imencode('.jpg', contact)
    assert ok
    encoded.tofile(root / 'output/editing-contact.jpg')
    reference = ROOT / 'tests/fixtures/editing-v1.reference.json'
    data = {'version': 1, 'size': [360, 640], 'sample_size': [9, 16], 'samples': signatures}
    if args.update_reference:
        write_json(reference, data)
    expected_data = read_json(reference)
    assert expected_data['samples'].keys() == signatures.keys(), 'The fixture timeline changed; review and update its baseline explicitly'
    errors = {key: float(np.abs(np.array(value, dtype=float) - np.array(expected_data['samples'][key], dtype=float)).mean()) for key, value in signatures.items()}
    assert max(errors.values()) < 5, f'Visual regression: {errors}'
    write_json(root / 'output/editing-regression.json', {'passed': True, 'effects': 16, 'visual_samples': len(signatures),
               'freeze_pixel_difference': freeze_diff, 'ramp_source_matches': ramp_matches,
               'max_reference_difference': max(errors.values()), 'loudness': receipt['loudness'],
               'sfx_attack_level': attack, 'sfx_before_level': before, 'sfx_after_level': after,
               'scope': 'Engineering checks, not an aesthetic or human-editor benchmark'})
    print(json.dumps({'passed': True, 'effects': 16, 'visual_samples': len(signatures), 'freeze_pixel_difference': freeze_diff, 'ramp_source_matches': ramp_matches}))


if __name__ == '__main__':
    main()

"""Real Remotion regression: source trim, speed, cut boundaries, independent audio timing.

Run explicitly: python tests/render_smoke.py. Uses only local generated media, no VOICEVOX.
"""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import REPO_ROOT, find_executable, read_json, run, write_json
from video import run_worker
from production import load_project, prepare


def main():
    root = REPO_ROOT / 'projects/render-smoke'
    (root / 'work').mkdir(parents=True, exist_ok=True)
    ffmpeg = find_executable('ffmpeg')
    run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=320x180:r=30:d=1',
         '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=30:d=1',
         '-f', 'lavfi', '-i', 'color=c=lime:s=320x180:r=30:d=1',
         '-filter_complex', '[0:v][1:v][2:v]concat=n=3:v=1:a=0[out]', '-map', '[out]',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', root / 'source.mp4'], capture=True)
    run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3:sample_rate=48000', root / 'tone.wav'], capture=True)
    run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', '3', root / 'silent.wav'], capture=True)
    write_json(root / 'project.json', {
        'title': 'render-smoke', 'video': {'width': 360, 'height': 640, 'fps': 30},
        'beats': [{'id': 'test', 'duration': 2}],
        'shots': [{'path': 'source.mp4', 'to': 1, 'source_start': 1},
                  {'path': 'source.mp4', 'from': 1, 'source_start': 0, 'speed': 2}],
        'audio': [{'path': 'tone.wav', 'from': .4, 'to': 1.6, 'source_start': .5}]
    })
    silent = load_project(root)
    silent['audio'][0]['path'] = 'silent.wav'
    assert any('無音' in warning for warning in prepare(root, silent)['warnings'])
    if run_worker(root, 'final'):
        raise RuntimeError(read_json(root / 'work/job.json'))
    movie = root / 'output/render-smoke.mp4'
    def rgb(second):
        p = subprocess.run([str(ffmpeg), '-v', 'error', '-ss', str(second), '-i', str(movie),
                            '-frames:v', '1', '-vf', 'scale=1:1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], check=True, capture_output=True)
        return tuple(p.stdout[:3])
    colors = [rgb(t) for t in [0, .96, 1, 1.46, 1.5, 1.96]]
    assert all(c[2] > 200 and c[0] < 20 for c in [colors[0], colors[1], colors[4], colors[5]]), colors
    assert all(c[0] > 200 and c[2] < 20 for c in [colors[2], colors[3]]), colors
    import array, math
    p = subprocess.run([str(ffmpeg), '-v', 'error', '-i', str(movie), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'], check=True, capture_output=True)
    samples = array.array('f', p.stdout)
    def rms(start, end):
        values = samples[int(start * 48000):int(end * 48000)]
        return math.sqrt(sum(v * v for v in values) / len(values))
    levels = [rms(a,b) for a,b in [(0,.3),(.5,1.5),(1.7,1.95)]]
    assert levels[0] < .001 and levels[2] < .001 and levels[1] > .03, levels
    write_json(root / 'output/smoke-result.json', {'passed': True, 'colors': colors, 'audio_rms': levels,
        'verified': ['source trim uses composition frames', 'speed consumes correct source time', 'cuts switch on exact frame', 'audio plays only in its independent interval', 'silent source audio is reported', 'output decode and loudness']})
    print(json.dumps({'passed': True, 'frames_checked': 6, 'audio_intervals_checked': 3}))


if __name__ == '__main__':
    main()

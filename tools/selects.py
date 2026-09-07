"""Source contact sheets using PySceneDetect. Detection proposes cuts, never chooses a story."""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from common import ffprobe, find_executable, run, write_json


def make_selects(source: Path, destination: Path) -> dict:
    from scenedetect import detect, AdaptiveDetector
    source = source.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    spans = detect(str(source), AdaptiveDetector(), show_progress=False)
    length = float(ffprobe(source)["format"]["duration"])
    ranges = [(a.seconds, b.seconds) for a, b in spans] or [(0, length)]
    rows, shots = [], []
    for i, (start, end) in enumerate(ranges):
        # Long uncut shots need several samples too; a midpoint alone hides the action.
        count = max(3, min(12, int((end - start) / 4) + 1))
        times = [start + (end - start) * (j + 0.5) / count for j in range(count)]
        images = []
        for j, second in enumerate(times):
            filename = f"scene-{i + 1:03}-{j + 1:02}.jpg"
            run([find_executable("ffmpeg"), "-v", "error", "-y", "-ss", str(second), "-i", source,
                 "-frames:v", "1", "-vf", "scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2", destination / filename], capture=True)
            images.append(f'<figure><img src="{filename}"><figcaption>{second:.2f}s</figcaption></figure>')
        shots.append({"scene": i + 1, "from": start, "to": end, "samples": times})
        rows.append(f'<section><h2>{i + 1} · {start:.2f}–{end:.2f}s</h2><div>{"".join(images)}</div></section>')
    write_json(destination / "scenes.json", {"source": str(source), "scenes": shots})
    (destination / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>素材を見る</title><style>body{background:#121212;color:#eee;font:16px sans-serif;margin:32px}section>div{display:flex;flex-wrap:wrap}figure{margin:8px}img{width:320px}figcaption{padding:6px}</style><h1>' + html.escape(source.name) + '</h1>' + ''.join(rows), encoding='utf-8')
    return {"scenes": len(shots), "review": str(destination / "index.html")}


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(make_selects(args.source, args.out), ensure_ascii=False))

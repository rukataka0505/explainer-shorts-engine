"""A video and frame contact sheet for actual editorial review; no aesthetic scoring."""
from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from common import final_output_path, find_executable, read_json, run


def create_review(root: Path, quality: str) -> dict:
    project = read_json(root / 'project.json')
    timing = read_json(root / 'work/timing.json')
    output = root / 'output/preview.mp4' if quality == 'preview' else final_output_path(root, project)
    if not output.is_file():
        raise ValueError('先にbuildしてください')
    receipt = read_json(root / f'output/{quality}-validation.json')
    import hashlib
    if receipt.get('project_sha256') != hashlib.sha256((root / 'project.json').read_bytes()).hexdigest() or receipt.get('sha256') != hashlib.sha256(output.read_bytes()).hexdigest():
        raise ValueError('レビュー対象が現在のproject.jsonと一致しません。buildしてください')
    folder = root / f'work/review-{quality}'
    folder.mkdir(parents=True, exist_ok=True)
    fps = timing['video']['fps']
    rows = []
    reasons = {s.get('id', f'shot-{i + 1}'): s.get('reason', '') for i, s in enumerate(project['shots'])}
    for i, shot in enumerate(timing['shots']):
        frames = [shot['from'], (shot['from'] + shot['to'] - 1) // 2, shot['to'] - 1]
        images = []
        for j, f in enumerate(frames):
            name = f'{i:03}-{j}.jpg'
            run([find_executable('ffmpeg'), '-v', 'error', '-y', '-ss', str(f / fps), '-i', output,
                 '-frames:v', '1', '-vf', 'scale=216:384', folder / name], capture=True)
            images.append(f'<button data-t="{f / fps}"><img src="{name}"><span>{f / fps:.2f}s</span></button>')
        start, end = shot['from'] / fps, shot['to'] / fps
        narration = ' '.join(l['text'] for l in timing['lines'] if l['from'] < shot['to'] and l['to'] > shot['from'])
        rows.append(f'<section><h2>{i + 1:02} · {start:.2f}–{end:.2f}s</h2><p>{html.escape(narration)}</p><div class="strip">{"".join(images)}</div><p>{html.escape(reasons.get(shot["id"], ""))}</p><small>{html.escape(shot["path"])} · source {shot["source_start"]:.2f}s</small></section>')
    movie = '../../' + quote(output.relative_to(root).as_posix(), safe='/')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Shorts review</title>
<style>body{margin:0;background:#111;color:#eee;font:15px/1.6 system-ui}main{max-width:1200px;margin:auto;display:grid;grid-template-columns:340px 1fr;gap:36px;padding:28px}aside{position:sticky;top:20px;height:90vh}video{width:100%;max-height:75vh;background:#000}h1{font-size:22px}h2{font-size:18px}section{border-top:1px solid #333;padding:14px 0 24px}.strip{display:flex;gap:8px}button{padding:0;border:0;background:#222;color:white;cursor:pointer;width:32%}img{width:100%;display:block}small{color:#aaa}@media(max-width:760px){main{display:block;padding:14px}aside{position:static;height:auto}video{height:65vh}.strip{gap:4px}}</style><main><aside><h1>__TITLE__</h1><video id="player" controls playsinline src="__MOVIE__"></video><p>画像を押すとその瞬間へ移動。</p><p>冒頭の引き／映像と説明／主役の構図／音のつなぎ／結末を、再生して確認。</p></aside><article>__ROWS__</article></main><script>const p=document.querySelector('video');document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{p.currentTime=Number(b.dataset.t);p.play()});</script></html>'''
    (folder / 'index.html').write_text(page.replace('__TITLE__', html.escape(project['title'])).replace('__MOVIE__', movie).replace('__ROWS__', ''.join(rows)), encoding='utf-8')
    return {'review': str(folder / 'index.html'), 'shots': len(rows), 'duration': timing['durationInFrames'] / fps}

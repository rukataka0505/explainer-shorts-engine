"""A video and frame contact sheet for actual editorial review; no aesthetic scoring."""
from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from common import final_output_path, find_executable, read_json, run


def verify_timing(receipt, timing):
    from production import timing_digest
    if receipt.get('timing_sha256') and receipt['timing_sha256'] != timing_digest(timing):
        raise ValueError('時間表がレンダー時の内容と一致しません。buildしてください')


def create_review(root: Path, quality: str) -> dict:
    project = read_json(root / 'project.json')
    timing = read_json(root / 'work/timing.json')
    output = root / 'output/preview.mp4' if quality == 'preview' else final_output_path(root, project)
    if not output.is_file():
        raise ValueError('先にbuildしてください')
    receipt = read_json(root / f'output/{quality}-validation.json')
    verify_timing(receipt, timing)
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
    groups = {}
    for event in timing.get('editing', {}).get('events', []):
        groups.setdefault(event['group'], []).append(event)
    for i, events in enumerate(groups.values()):
        first, last = min(e['from'] for e in events), max(e['to'] for e in events)
        frames = sorted({max(0, first - 1), events[0]['sync_frame'], last - 1, min(timing['durationInFrames'] - 1, last)})
        images = []
        for j, f in enumerate(frames):
            name = f'effect-{i:03}-{j}.jpg'
            run([find_executable('ffmpeg'), '-v', 'error', '-y', '-ss', str(f / fps), '-i', output,
                 '-frames:v', '1', '-vf', 'scale=216:384', folder / name], capture=True)
            images.append(f'<button data-t="{f / fps}"><img src="{name}"><span>{f / fps:.3f}s</span></button>')
        cue = next((s for s in timing['audio'] if s.get('role') == 'sfx:' + events[0]['group']), None)
        sound = f' · SE同期 {cue["sync_frame"] / fps:.3f}s' if cue else ''
        rows.append(f'<section><h2>{html.escape(events[0]["group"])} · {first / fps:.3f}s</h2><p>{html.escape(events[0]["reason"])}</p><div class="strip">{"".join(images)}</div><small>{html.escape(" + ".join(e["effect"] for e in events))}{sound}</small><p><button data-t="{max(0, first / fps - .7)}" data-end="{min(timing["durationInFrames"] / fps, last / fps + .8)}">前後を音付き再生</button></p></section>')
    movie = '../../' + quote(output.relative_to(root).as_posix(), safe='/')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Shorts review</title>
<style>body{margin:0;background:#111;color:#eee;font:15px/1.6 system-ui}main{max-width:1200px;margin:auto;display:grid;grid-template-columns:340px 1fr;gap:36px;padding:28px}aside{position:sticky;top:20px;height:90vh}video{width:100%;max-height:75vh;background:#000}h1{font-size:22px}h2{font-size:18px}section{border-top:1px solid #333;padding:14px 0 24px}.strip{display:flex;gap:8px}button{padding:0;border:0;background:#222;color:white;cursor:pointer;width:32%}img{width:100%;display:block}small{color:#aaa}@media(max-width:760px){main{display:block;padding:14px}aside{position:static;height:auto}video{height:65vh}.strip{gap:4px}}</style><main><aside><h1>__TITLE__</h1><video id="player" controls playsinline src="__MOVIE__"></video><p>画像を押すとその瞬間へ移動。</p><p>冒頭の引き／映像と説明／主役の構図／音のつなぎ／結末を、再生して確認。</p></aside><article>__ROWS__</article></main><script>const p=document.querySelector('video');document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{p.currentTime=Number(b.dataset.t);p.play()});</script></html>'''
    page = page.replace("const p=document.querySelector('video');document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{p.currentTime=Number(b.dataset.t);p.play()});",
                        "const p=document.querySelector('video');let stopAt=Infinity;document.querySelectorAll('[data-t]').forEach(b=>b.onclick=()=>{stopAt=Number(b.dataset.end||Infinity);p.currentTime=Number(b.dataset.t);p.muted=false;p.play()});p.addEventListener('timeupdate',()=>{if(p.currentTime>=stopAt){p.pause();stopAt=Infinity}});")
    warnings = ''.join('<p>' + html.escape(w) + '</p>' for w in timing.get('warnings', []))
    (folder / 'index.html').write_text(page.replace('__TITLE__', html.escape(project['title'])).replace('__MOVIE__', movie).replace('__ROWS__', warnings + ''.join(rows)), encoding='utf-8')
    return {'review': str(folder / 'index.html'), 'shots': len(timing['shots']), 'effect_groups': len(groups), 'duration': timing['durationInFrames'] / fps}


def create_comparison(root: Path, baseline: Path, quality: str) -> dict:
    """Compare identical narration at line anchors, including edits that change gaps."""
    import hashlib
    import os
    tracks = []
    folder = root / 'work/compare'
    folder.mkdir(parents=True, exist_ok=True)
    for directory in (baseline, root):
        p = read_json(directory / 'project.json')
        receipt = read_json(directory / f'output/{quality}-validation.json')
        movie = directory / ('output/preview.mp4' if quality == 'preview' else 'output/' + Path(receipt['file']).name)
        if not receipt.get('passed') or receipt.get('project_sha256') != hashlib.sha256((directory / 'project.json').read_bytes()).hexdigest() or receipt.get('sha256') != hashlib.sha256(movie.read_bytes()).hexdigest():
            raise ValueError('比較対象の検証結果が現在のproject/動画と一致しません')
        timing = read_json(directory / 'work/timing.json')
        verify_timing(receipt, timing)
        tracks.append({'src': quote(os.path.relpath(movie, folder).replace('\\', '/'), safe='/'), 'timing': timing, 'title': p['title']})
    a, b = tracks
    if [(l['id'], l['text']) for l in a['timing']['lines']] != [(l['id'], l['text']) for l in b['timing']['lines']]:
        raise ValueError('A/B比較は同じ原稿・line IDを使用してください')
    buttons = ''.join(f'<button data-a="{la["from"] / a["timing"]["video"]["fps"]}" data-b="{lb["from"] / b["timing"]["video"]["fps"]}">{html.escape(lb["text"])}</button>' for la, lb in zip(a['timing']['lines'], b['timing']['lines']))
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>編集 A/B 比較</title>
<style>*{box-sizing:border-box}body{background:#101614;color:#e9f2eb;font:16px/1.6 system-ui;margin:0}main{width:100%;max-width:1050px;margin:24px auto;padding:0 20px}h1{font-size:26px}p{color:#c6d6cb}.videos{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px}.videos section{min-width:0}video{display:block;width:100%;max-width:100%;height:65vh;object-fit:contain;background:#000}button{font:inherit;border:1px solid #3c5b46;color:#e6ffee;background:#1b3325;padding:10px 14px;border-radius:8px;cursor:pointer;margin:4px}nav{margin:20px 0}#lines button{display:block;width:calc(100% - 8px);text-align:left}@media(max-width:600px){.videos{gap:10px}video{height:45vh}}</style>
<main><h1>編集 A/B 比較</h1><p>同じ原稿・実写素材で比較。無音の整理により尺は異なります。下の原稿を押すと、両方を発話の開始位置へ移動します。</p>
<div class="videos"><section><h2>A · 演出なし</h2><video id="a" controls playsinline preload="auto" src="__A__"></video></section><section><h2>B · 編集文法あり</h2><video id="b" controls playsinline preload="auto" src="__B__"></video></section></div>
<nav><button id="play-a">Aを音付き再生</button><button id="play-b">Bを音付き再生</button><button id="pause">停止</button><button id="slow">通常 / 0.5倍</button></nav><div id="lines">__LINES__</div>
<p>演出の効果、字幕の読みやすさ、視線の移動、音の強さを見比べてください。再生数や人手編集より優れていることを証明する比較ではありません。</p></main>
<script>const a=document.querySelector('#a'),b=document.querySelector('#b');document.querySelector('#play-a').onclick=()=>{b.pause();a.muted=false;a.play()};document.querySelector('#play-b').onclick=()=>{a.pause();b.muted=false;b.play()};document.querySelector('#pause').onclick=()=>{a.pause();b.pause()};document.querySelector('#slow').onclick=()=>{a.playbackRate=b.playbackRate=b.playbackRate===1?.5:1};document.querySelectorAll('[data-a]').forEach(button=>button.onclick=()=>{a.pause();b.pause();a.currentTime=Number(button.dataset.a);b.currentTime=Number(button.dataset.b)});</script></html>'''
    target = folder / 'index.html'
    target.write_text(page.replace('__A__', a['src']).replace('__B__', b['src']).replace('__LINES__', buttons), encoding='utf-8')
    return {'comparison': str(target), 'quality': quality, 'baseline': str(baseline), 'edited': str(root)}

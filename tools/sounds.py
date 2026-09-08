"""Small reproducible sound bank. Binary assets stay in .cache and projects."""
from __future__ import annotations

import hashlib
import html
import shutil
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

from common import REPO_ROOT, find_executable, project_file, read_json, write_json

BANK = REPO_ROOT / 'editing/sounds.v1.json'
CACHE = REPO_ROOT / '.cache/sounds'


def entries(query=''):
    items = read_json(BANK)['sounds']
    terms = query.lower().split()
    return [x for x in items if all(q in ' '.join([x['id'], x['label'], *x['tags']]).lower() for q in terms)]


def fetch(item):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (item['id'] + '.wav')
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == item['sha256']:
        return target
    with urllib.request.urlopen(item['url'], timeout=30) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError(f"音源のハッシュが一致しません: {item['id']}")
    temp = target.with_suffix('.download')
    temp.write_bytes(data)
    temp.replace(target)
    return target


def measure(path):
    raw = subprocess.check_output([str(find_executable('ffmpeg')), '-v', 'error', '-i', str(path),
                                   '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    samples = np.frombuffer(raw, dtype='<f4')
    if not len(samples) or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 1e-4:
        raise ValueError(f'音源が空または無音です: {path}')
    peak = float(np.max(np.abs(samples)))
    return {'duration': len(samples) / 48000, 'peak_dbfs': round(20 * np.log10(peak), 3),
            'marker': round(int(np.argmax(np.abs(samples))) / 48000, 6)}


def audition(items):
    CACHE.mkdir(parents=True, exist_ok=True)
    cards = []
    for item in items:
        path = fetch(item)
        measure(path)
        tags = ' '.join(item['tags'])
        cards.append(f'<section><h2>{html.escape(item["label"])}</h2><p>{html.escape(item["id"] + " · " + tags)}</p>'
                     f'<audio controls preload="none" src="{path.name}"></audio>'
                     '<p>機械検査済・採用場面での試聴は未確認</p></section>')
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><title>SE試聴棚</title>
<style>body{background:#14181d;color:#eee;font:16px/1.6 system-ui;max-width:960px;margin:40px auto;padding:20px}section{border-top:1px solid #46505b;padding:12px}input{padding:12px;width:90%}audio{width:90%}h2{font-size:20px}</style>
<h1>SE試聴棚</h1><p>用途で検索し、再生して選ぶ。現場の記録音とは区別する。採用後は声との重なりも確認。</p>
<input id="search" placeholder="確認、切替、疑問、click …" aria-label="音を検索">__CARDS__
<script>document.querySelector('#search').oninput=e=>{const q=e.target.value.toLowerCase().split(/\\s+/);document.querySelectorAll('section').forEach(s=>s.hidden=!q.every(t=>s.textContent.toLowerCase().includes(t)))};
document.querySelectorAll('audio').forEach(a=>{a.volume=.35;a.onplay=()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})});</script></html>'''
    target = CACHE / 'index.html'
    target.write_text(page.replace('__CARDS__', ''.join(cards)), encoding='utf-8')
    return {'count': len(items), 'audition': str(target)}


def import_sound(root, sound_id):
    matches = [x for x in entries() if x['id'] == sound_id]
    if not matches:
        raise ValueError(f'未登録の音です: {sound_id}')
    item = matches[0]
    path = root / 'project.json'
    project = read_json(path)
    config = project.setdefault('editing', {'version': 1})
    sounds = config.setdefault('sounds', {})
    relative = f'assets/sfx/{sound_id}.wav'
    spec = {'path': relative, 'marker': item['marker'], 'volume': item['volume']}
    if sound_id in sounds and sounds[sound_id] != spec:
        raise ValueError(f'既存の音設定を保護しました: {sound_id}')
    target = project_file(root, relative)
    source = fetch(item)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError(f'既存音源が異なります: {relative}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('取り込み音源の読み戻しが一致しません')
    sounds[sound_id] = spec
    write_json(path, project)
    return {'sound': sound_id, 'path': relative, 'registered': True,
            'note': '未配置。試聴してediting.eventsのaudio.sfxまたはaudioへ採用し、sound_designへ理由と参照を記入してください'}

"""Fetch NASA primary footage and create a local, reproducible editing example."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from common import find_executable
SOURCES = {
    'water.mp4': 'KSC-20190913-RV-CMS01_0001-Nominal_Wet_Flow_Test_at_Pad_39B-3229665',
    'drone.mp4': 'KSC-20190914-RV-ILW01_0001-Nominal_Wet_Flow_Test_at_Pad_39B-3231741',
    'launch.mp4': 'Artemis I Launch 2022 CU tracking from Press Site_compressed',
}
AUDIO_SOURCE = 'KSC-20221116-MH-WEL01-0001-Artemis_I_Launch_Imagery-3319254'

def main():
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'projects/demo-water'
    (destination / 'assets').mkdir(parents=True, exist_ok=True)
    for filename, identifier in SOURCES.items():
        path = destination / 'assets' / filename
        if path.exists():
            continue
        with urllib.request.urlopen('https://images-api.nasa.gov/asset/' + urllib.parse.quote(identifier, safe=''), timeout=30) as r:
            items = json.load(r)['collection']['items']
        # Original camera footage; proxies are not the final source.
        urls = [x['href'].replace('http:', 'https:', 1) for x in items]
        url = urllib.parse.quote(next(x for x in urls if x.endswith('~orig.mp4')), safe=':/%~')
        temp = path.with_suffix('.download')
        with urllib.request.urlopen(url, timeout=120) as r, temp.open('wb') as out:
            shutil.copyfileobj(r, out)
        temp.replace(path)
        print(json.dumps({'downloaded': filename, 'bytes': path.stat().st_size}), flush=True)
    sound = destination / 'assets/launch-sound.wav'
    if not sound.exists():
        with urllib.request.urlopen('https://images-api.nasa.gov/asset/' + AUDIO_SOURCE, timeout=30) as r:
            items = json.load(r)['collection']['items']
        url = urllib.parse.quote(next(x['href'] for x in items if x['href'].endswith('~orig.mp4')).replace('http:', 'https:', 1), safe=':/%~')
        temporary = sound.with_name('launch-sound.tmp.wav')
        subprocess.run([str(find_executable('ffmpeg')), '-v', 'error', '-y', '-ss', '35', '-i', url,
                        '-t', '15', '-vn', '-ar', '48000', '-c:a', 'pcm_s16le', str(temporary)], check=True)
        temporary.replace(sound)
        print(json.dumps({'extracted_audio': sound.name, 'source_start': 35}), flush=True)
    if not (destination / 'project.json').exists():
        shutil.copyfile(ROOT / 'examples/water.project.json', destination / 'project.json')
    print(json.dumps({'project': str(destination)}, ensure_ascii=False))

if __name__ == '__main__':
    main()

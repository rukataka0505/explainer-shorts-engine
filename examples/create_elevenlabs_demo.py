"""Reproduce the NASA edit with the default ElevenLabs voice and full captions."""
import json
import sys
from pathlib import Path
from create_demo import ROOT, main as fetch_demo


def main():
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'projects/elevenlabs-preview'
    project_file = destination / 'project.json'
    existed = project_file.exists()
    sys.argv = [sys.argv[0], str(destination)]
    fetch_demo()
    if not existed:
        project = json.loads(project_file.read_text(encoding='utf-8'))
        project['voices'] = {'narrator': {'provider': 'elevenlabs'}}
        project['title'] = 'ElevenLabs字幕検証'
        project.get('youtube', {}).pop('description', None)
        project_file.write_text(json.dumps(project, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

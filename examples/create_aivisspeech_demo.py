"""Download NASA sources and reproduce the short AivisSpeech sample."""
import shutil
import sys
from pathlib import Path
from create_demo import ROOT, main as fetch_demo


def main():
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'projects/aivisspeech-nise-sample'
    existed = (destination / 'project.json').exists()
    sys.argv = [sys.argv[0], str(destination)]
    fetch_demo()
    if not existed:
        shutil.copyfile(ROOT / 'examples/aivisspeech.project.json', destination / 'project.json')


if __name__ == '__main__':
    main()

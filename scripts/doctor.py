"""Check a fresh clone's dependencies and bundled assets without API calls."""
import platform
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from studio.audio import ffmpeg
from studio.config import ROOT
from studio.deck_catalog import deck_options
from studio.daily_visuals import gallery


def main():
    print(f'Platform: {platform.system()} {platform.machine()} | Python {platform.python_version()}')
    assert sys.version_info>=(3,11),'Python 3.11+ is required.'
    result=subprocess.run([ffmpeg(),'-version'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,'Bundled FFmpeg did not run on this architecture.'
    print('FFmpeg:',result.stdout.splitlines()[0])
    assert all(d['ready'] for d in deck_options(ROOT)),'A tarot deck has missing artwork.'
    for style in ('esoteric-minimal','storybook-cartoon'):
        assert all(c['ready'] for c in gallery(style)),f'Missing {style} daily cards.'
    assert (ROOT/'frontend/dist/index.html').is_file(),'Build the frontend first.'
    print('All three tarot decks, both daily card collections, and editor build are present.')
    if sys.platform=='darwin':
        assert Path('/usr/bin/say').is_file(),'macOS say is unavailable; use captions only or an OpenAI voice.'
        print('Free native macOS narration is available. No OpenAI key is required.')
    print('Studio is ready to start at http://127.0.0.1:5057.')


if __name__=='__main__':main()

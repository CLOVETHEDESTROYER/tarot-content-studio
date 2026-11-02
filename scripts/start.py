"""Start the local studio and open its browser on macOS (or other platforms)."""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from studio.config import ROOT  # loads optional local .env before reading the port


def main():
    port=int(os.getenv('STUDIO_PORT','5057'))
    url=f'http://127.0.0.1:{port}'
    if not (ROOT/'frontend/dist/index.html').is_file():
        raise SystemExit('Run Setup Content Studio.command first to build the editor.')
    def is_running():
        try:
            with urllib.request.urlopen(url+'/api/config',timeout=1) as response:
                return json.load(response).get('application')=='starpower-content-studio'
        except (OSError,ValueError,urllib.error.URLError):return False
    if is_running():
        print(f'Studio already running: {url}')
        if os.getenv('STUDIO_NO_BROWSER')!='1':webbrowser.open(url)
        return
    from app import create_app
    from waitress import serve
    print(f'StarPower Content Studio: {url}\nKeep this window open. Press Ctrl+C to stop.',flush=True)
    browser_timer=threading.Timer(2,lambda: webbrowser.open(url) if is_running() else None)
    browser_timer.daemon=True
    if os.getenv('STUDIO_NO_BROWSER')!='1':browser_timer.start()
    try:serve(create_app(),host='127.0.0.1',port=port,threads=8)
    except KeyboardInterrupt:pass
    finally:browser_timer.cancel()


if __name__=='__main__':main()

"""Fresh-install video smoke test. Uses native narration; never calls OpenAI."""
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from studio.audio import ffmpeg,wave_info
from studio.daily import create_daily
from studio.jobs import Jobs
from studio.platform_support import default_voice
from studio.store import Store


def verify(folder):
    folder.mkdir(parents=True,exist_ok=True)
    with patch('studio.daily_context.DATA',folder/'data'),patch('studio.jobs.DATA',folder/'data'),patch('studio.jobs.EXPORTS',folder/'exports'):
        store=Store(folder/'data/studio.sqlite3');jobs=Jobs(store)
        try:
            draft=store.create(create_daily(dict(reading_type='numerology',date='2026-11-02',edition='evening',
                                               voice=default_voice(),writer='local',style='storybook-cartoon',duration=30)))
            job=jobs.submit(draft,'export');limit=time.monotonic()+240
            while job['status'] in ('queued','running') and time.monotonic()<limit:
                time.sleep(1);job=store.get_job(job['id'])
            assert job['status']=='done',job.get('error') or 'Export did not finish within four minutes.'
            destination=folder/'exports'/job['id'];video=destination/'reading.mp4'
            decoded=subprocess.run([ffmpeg(),'-hide_banner','-i',str(video),'-f','null','-'],capture_output=True,text=True,timeout=60)
            assert decoded.returncode==0,decoded.stderr
            assert all(value in decoded.stderr for value in ('1080x1920','30 fps','h264','aac'))
            timeline=json.loads((destination/'timeline.json').read_text(encoding='utf-8'))
            assert all(s['start']<s['end'] for s in timeline['sections'])
            assert all(c['start']<c['end'] for c in timeline['captions'])
            if default_voice()!='silent':wave_info(folder/'data/prepared'/job['fingerprint']/'narration.wav')
            with zipfile.ZipFile(destination/'posting-bundle.zip') as bundle:assert bundle.testzip() is None
            print(f"PASS: native {default_voice()} narration, all section transitions, captions, 1080x1920 H264/AAC MP4, full decode, posting bundle.")
            print(f"Output: {destination}")
        finally:jobs.pool.shutdown(wait=True)


if __name__=='__main__':
    if os.getenv('STUDIO_SMOKE_OUTPUT'):verify(Path(os.environ['STUDIO_SMOKE_OUTPUT']).resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='starpower-smoke-') as temp:verify(Path(temp))

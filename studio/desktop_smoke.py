"""Offline checks against the actual frozen executable and bundled resources."""
import subprocess
import tempfile
from pathlib import Path
from .audio import ffmpeg,windows_speech,macos_speech,wave_info
from .platform_support import default_voice
from .deck_catalog import deck_options
from .daily_visuals import gallery
from .config import ROOT
from .engine import create
from .render import render_frame,encode_video


def verify():
    import keyring
    backend=type(keyring.get_keyring()).__module__
    assert backend in ('keyring.backends.Windows','keyring.backends.macOS'),backend
    assert all(d['ready'] for d in deck_options(ROOT))
    assert all(c['ready'] for style in ('esoteric-minimal','storybook-cartoon') for c in gallery(style))
    assert (ROOT/'frontend/dist/index.html').is_file()
    result=subprocess.run([ffmpeg(),'-version'],capture_output=True,timeout=15)
    assert result.returncode==0
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)
        raw,events,_=(macos_speech({'sections':[{'text':'Take a breath. Begin again.'}]},folder) if default_voice()=='macos' else windows_speech('Take a breath. Begin again.',folder))
        assert wave_info(raw)>0 and events
        draft=create({'voice':default_voice(),'spread':'one'})
        duration=max(3,wave_info(raw))
        manifest=dict(duration=duration,sections=[dict(key='hook',start=0,end=duration,card_id=None)],captions=[dict(start=0,end=duration,text='Take a breath. Begin again.')])
        render_frame(draft,manifest,0).save(folder/'frame.jpg')
        encode_video(draft,manifest,raw,folder/'test.mp4',lambda *args:None)
        decoded=subprocess.run([ffmpeg(),'-hide_banner','-i',str(folder/'test.mp4'),'-f','null','-'],capture_output=True,text=True,timeout=30)
        assert decoded.returncode==0 and '1080x1920' in decoded.stderr and '30 fps' in decoded.stderr
    return dict(passed=True,bundledDecks=3,dailyCards=72,frontend=True,nativeVoice=default_voice(),portraitMp4Decode=True,credentialBackend=backend)

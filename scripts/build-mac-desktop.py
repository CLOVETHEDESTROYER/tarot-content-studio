"""Build an Intel .app with an embedded Python runtime, artwork and FFmpeg."""
import json
import platform
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def main():
    if sys.platform!='darwin' or platform.machine()!='x86_64':
        raise SystemExit('Build on an Intel Mac with Intel Python.')
    from PIL import Image
    metadata=json.loads((ROOT/'resources/desktop-release.json').read_text())
    build=ROOT/'build/desktop';build.mkdir(parents=True,exist_ok=True)
    with Image.open(ROOT/'assets/glyph-gold.png') as source:
        icon=Image.new('RGBA',(1024,1024),'#103b28');source.thumbnail((720,720))
        icon.alpha_composite(source.convert('RGBA'),((1024-source.width)//2,(1024-source.height)//2))
        icon.save(build/'studio.icns')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
        '--name','StarPower Content Studio','--distpath',str(ROOT/'desktop-dist'),
        '--workpath',str(build/'work'),'--specpath',str(build),'--icon',str(build/'studio.icns'),
        '--osx-bundle-identifier',metadata['bundleIdentifier'],'--target-architecture','x86_64',
        '--collect-all','TikTokLive','--collect-all','TikTokLiveProto','--collect-all','EulerApiSdk','--collect-all','webview','--collect-all','imageio_ffmpeg','--collect-all','keyring',
        '--hidden-import','webview.platforms.cocoa','--hidden-import','studio.desktop_smoke',
        '--hidden-import','studio.speech_worker','--exclude-module','PyQt5','--exclude-module','PyQt6',
        '--exclude-module','PySide2','--exclude-module','PySide6']
    for source,target in [('assets','assets'),('frontend/dist','frontend/dist'),('resources','resources')]:
        command+=['--add-data',str(ROOT/source)+':'+target]
    subprocess.run([*command,str(ROOT/'desktop.py')],cwd=ROOT,check=True)
    app=ROOT/'desktop-dist/StarPower Content Studio.app'
    path=app/'Contents/Info.plist';info=plistlib.loads(path.read_bytes())
    info.update(CFBundleShortVersionString=metadata['version'],CFBundleVersion=str(metadata['build']),
                LSMinimumSystemVersion='15.0',NSHighResolutionCapable=True,
                NSMicrophoneUsageDescription='The studio does not record audio. Narration uses the system voice.')
    path.write_bytes(plistlib.dumps(info))
    # Personal distribution: ad-hoc signature, without pretending to be notarized.
    subprocess.run(['/usr/bin/codesign','--force','--deep','--sign','-',str(app)],check=True)
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
    sys.path.insert(0,str(ROOT))
    from studio.updates import validate_app
    validate_app(app,metadata['version'])
    print(app)


if __name__=='__main__':main()

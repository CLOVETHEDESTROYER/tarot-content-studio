"""Build a self-contained Windows directory app; do not ship credentials/data."""
import subprocess
import sys
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


def main():
    if sys.platform!='win32':raise SystemExit('Build the Windows desktop package on Windows.')
    parser=argparse.ArgumentParser();parser.add_argument('--distpath',type=Path,default=ROOT/'desktop-dist')
    args=parser.parse_args()
    from PIL import Image
    build=ROOT/'build/desktop';build.mkdir(parents=True,exist_ok=True)
    with Image.open(ROOT/'assets/glyph-gold.png') as image:
        icon=Image.new('RGBA',(256,256),'#103b28');image.thumbnail((180,180));icon.alpha_composite(image.convert('RGBA'),((256-image.width)//2,(256-image.height)//2));icon.save(build/'studio.ico')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--name','StarPower Content Studio',
        '--distpath',str(args.distpath),'--workpath',str(build/'work'),'--specpath',str(build),'--icon',str(build/'studio.ico'),
        '--manifest',str(ROOT/'resources/windows.manifest'),
        '--collect-all','webview','--collect-all','imageio_ffmpeg','--collect-all','clr_loader','--collect-all','keyring','--hidden-import','studio.speech_worker',
        '--hidden-import','studio.desktop_smoke','--hidden-import','webview.platforms.edgechromium','--hidden-import','webview.platforms.winforms',
        '--exclude-module','PyQt5','--exclude-module','PyQt6','--exclude-module','PySide2','--exclude-module','PySide6']
    for source,target in [('assets','assets'),('frontend/dist','frontend/dist'),('resources','resources'),('scripts/speak.ps1','scripts')]:command+=['--add-data',str(ROOT/source)+';'+target]
    subprocess.run([*command,str(ROOT/'desktop.py')],cwd=ROOT,check=True)
    print(args.distpath/'StarPower Content Studio/StarPower Content Studio.exe')


if __name__=='__main__':main()

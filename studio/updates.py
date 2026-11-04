"""Private GitHub release updater. Installs never replace data or the exchange."""
import hashlib
import json
import logging
import os
import platform
import plistlib
import re
import shutil
import sqlite3
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path,PurePosixPath
import httpx
from .config import ROOT,DATA,EXPORTS
from .version import BUILD,VERSION
from .audio import HIDDEN
from . import operations

REPO='CLOVETHEDESTROYER/tarot-content-studio'
API='https://api.github.com/repos/'+REPO
APP='StarPower Content Studio'
MAX_ARCHIVE=1_500_000_000
MAX_EXPANDED=3_000_000_000


def filesystem_path(path):
    """ZIP extraction must support Windows paths beyond the legacy 260 limit."""
    path=str(Path(path).absolute())
    if sys.platform!='win32' or path.startswith('\\\\?\\'):return path
    return '\\\\?\\UNC\\'+path[2:] if path.startswith('\\\\') else '\\\\?\\'+path


def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,6}\.\d{1,6}\.\d{1,6}',value):raise ValueError('Invalid desktop version.')
    return tuple(map(int,value.split('.')))


def package_name(host=None):
    return 'StarPower-Content-Studio-'+('Mac-Intel' if (host or sys.platform)=='darwin' else 'Windows-x64')+'.zip'


def select_release(releases,current=VERSION,host=None):
    selected=[]
    for release in releases:
        tag=release.get('tag_name','')
        if release.get('draft') or release.get('prerelease') or not tag.startswith('desktop-v'):continue
        try:new=version(tag[9:])
        except ValueError:continue
        if new<=version(current) or release.get('html_url')!=f'https://github.com/{REPO}/releases/tag/{tag}':continue
        for asset in release.get('assets',[]):
            if (asset.get('name')==package_name(host) and asset.get('state')=='uploaded' and type(asset.get('size')) is int and 0<asset['size']<=MAX_ARCHIVE
                and re.fullmatch(r'sha256:[a-fA-F0-9]{64}',asset.get('digest') or '')
                and type(asset.get('id')) is int and asset['id']>0
                and asset.get('browser_download_url')==f'https://github.com/{REPO}/releases/download/{tag}/{package_name(host)}'):
                selected.append(dict(version=tag[9:],notes=release.get('body',''),url=release['html_url'],asset=asset))
    return max(selected,key=lambda r:version(r['version'])) if selected else None


def validate_archive(archive,host=None):
    mac=(host or sys.platform)=='darwin';top=APP+('.app' if mac else '')
    with zipfile.ZipFile(archive) as bundle:
        files=bundle.infolist()
        if not files or len(files)>30000 or sum(f.file_size for f in files)>MAX_EXPANDED:raise ValueError('Update archive exceeds the supported expanded size.')
        seen=set()
        for entry in files:
            name=entry.orig_filename;p=PurePosixPath(name)
            if ('\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=top
                or any(part.endswith((' ','.')) for part in p.parts) or name.casefold() in seen):raise ValueError('Update archive contains an unexpected or unsafe path.')
            seen.add(name.casefold())
            mode=entry.external_attr>>16
            if stat.S_ISLNK(mode):
                if not mac or entry.file_size>4096:raise ValueError('Unexpected link in update archive.')
                target=bundle.read(entry).decode('utf-8');parts=list(p.parent.parts)
                if target.startswith('/') or '\\' in target:raise ValueError('Update link escapes the app.')
                for part in PurePosixPath(target).parts:
                    if part=='..':
                        if len(parts)<=1:raise ValueError('Update link escapes the app.')
                        parts.pop()
                    elif part!='.':parts.append(part)
            elif stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR):raise ValueError('Unsupported update archive file type.')
    return top


def application_root(executable=None,host=None):
    executable=Path(executable or sys.executable).resolve()
    if (host or sys.platform)=='darwin':
        for p in executable.parents:
            if p.name==APP+'.app':return p
        raise ValueError('Run the installed Mac app to install updates.')
    if executable.name!=APP+'.exe' or executable.parent.name!=APP:raise ValueError('Run the packaged Windows app to install updates.')
    return executable.parent


def validate_app(folder,expected,host=None):
    mac=(host or sys.platform)=='darwin';folder=Path(folder)
    manifest=folder/('Contents/Resources/resources/desktop-release.json' if mac else '_internal/resources/desktop-release.json')
    info=json.loads(manifest.read_text(encoding='utf-8'))
    if any(info.get(k)!=BUILD[k] for k in ('application','bundleIdentifier','exchangeSchema','historySchema')) or info.get('version')!=expected:
        raise ValueError('Update identity, version, or history/exchange compatibility does not match.')
    if mac:
        if info['minimumMacOS']>int(platform.mac_ver()[0].split('.')[0]):raise ValueError('This update needs a newer macOS.')
        plist=plistlib.loads((folder/'Contents/Info.plist').read_bytes())
        if plist.get('CFBundleIdentifier')!=BUILD['bundleIdentifier'] or plist.get('CFBundleShortVersionString')!=expected:raise ValueError('Mac bundle identity does not match the release.')
        binary=folder/'Contents/MacOS'/APP
        header=binary.read_bytes()[:8]
        if len(header)<8 or struct.unpack('<II',header)!=(0xfeedfacf,0x01000007):raise ValueError('Update is not a native Intel Mac app.')
        subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(folder)],capture_output=True,check=True,timeout=60)
    else:
        with (folder/(APP+'.exe')).open('rb') as source:
            if source.read(2)!=b'MZ':raise ValueError('Invalid Windows executable.')
            source.seek(60);offset=struct.unpack('<I',source.read(4))[0];source.seek(offset)
            if source.read(6)!=b'PE\0\0\x64\x86':raise ValueError('Update is not a Windows x64 app.')
    return folder


class DesktopUpdates:
    def __init__(self,app,workspace=None):
        self.app=app;self.workspace=workspace;self.window=None;self.available=None;self.prepared=None
        self.lock=threading.Lock();self.cancel_event=threading.Event()
        self.cache=DATA.parent/'Updates';self.cache.mkdir(parents=True,exist_ok=True)
        self.info=dict(status='idle',current=VERSION,message='Check for a desktop update.',progress=0,available=None,
                       desktop=True,recoveryFolder=str(self.cache/'Recovery'),credentialStored=False)

    def update_state(self):
        with self.lock:return dict(self.info)

    def _state(self,**values):
        with self.lock:self.info.update(values)

    def _token(self):
        token=os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
        if token:return token
        try:
            import keyring
            token=keyring.get_password('StarPower Content Studio Updates','github')
            if token:return token
        except Exception:pass
        gh=shutil.which('gh')
        if gh:
            response=subprocess.run([gh,'auth','token'],capture_output=True,text=True,timeout=10,**HIDDEN)
            if response.returncode==0:return response.stdout.strip()
        return None

    def save_update_token(self,token):
        if not isinstance(token,str) or not 1<=len(token)<=500:raise ValueError('Enter a read-only GitHub repository token.')
        import keyring
        keyring.set_password('StarPower Content Studio Updates','github',token.strip())
        self._state(credentialStored=True,message='GitHub access saved in the operating system credential store.')
        return self.update_state()

    def _client(self,accept='application/vnd.github+json'):
        headers={'Accept':accept,'User-Agent':'StarPower-Content-Studio','X-GitHub-Api-Version':'2022-11-28'}
        token=self._token()
        if token:headers['Authorization']='Bearer '+token
        return httpx.Client(headers=headers,timeout=60,follow_redirects=True)

    def check_update(self):
        if self.update_state()['status'] in ('downloading','installing','waiting'):return self.update_state()
        self._state(status='checking',message='Checking private GitHub desktop releases…')
        try:
            with self._client() as client:response=client.get(API+'/releases',params={'per_page':100})
            if response.status_code in (401,403,404):raise ValueError('GitHub release access is unavailable. Sign in with GitHub CLI or save a read-only token for this private repository.')
            response.raise_for_status();self.available=select_release(response.json())
            public={k:self.available[k] for k in ('version','notes','url')} if self.available else None
            self._state(status='available' if public else 'current',available=public,message='Update available.' if public else 'This is the latest published desktop version.')
        except Exception as exc:self._state(status='error',message=str(exc) if isinstance(exc,ValueError) else 'Could not check GitHub releases. Your studio can keep working.')
        return self.update_state()

    def download_update(self):
        with self.lock:
            if self.info['status'] in ('downloading','installing','waiting'):return dict(self.info)
            if not self.available:raise ValueError('Check for an available update first.')
            self.info.update(status='downloading',progress=0,message='Downloading and verifying the desktop package…')
        self.cancel_event.clear()
        try:
            asset=self.available['asset']
            if shutil.disk_usage(self.cache).free<asset['size']*5+200_000_000:raise ValueError('Free more disk space for the download, extracted app, and rollback copy.')
            stage=self.cache/uuid.uuid4().hex;stage.mkdir();archive=stage/'package.zip';digest=hashlib.sha256();received=0
            with self._client('application/octet-stream') as client,client.stream('GET',API+'/releases/assets/'+str(asset['id'])) as response:
                response.raise_for_status()
                with archive.open('wb') as output:
                    for chunk in response.iter_bytes(1024*1024):
                        if self.cancel_event.is_set():raise ValueError('Download cancelled. The installed app was not changed.')
                        received+=len(chunk)
                        if received>asset['size']:raise ValueError('Download exceeded the release size.')
                        digest.update(chunk);output.write(chunk);self._state(progress=round(received/asset['size']*90))
            if received!=asset['size'] or 'sha256:'+digest.hexdigest()!=asset['digest'].lower():raise ValueError('Update size or checksum did not match GitHub. The installed app was not changed.')
            top=validate_archive(archive);unpacked=stage/'Unpacked';unpacked.mkdir()
            if sys.platform=='darwin':subprocess.run(['/usr/bin/ditto','-x','-k',str(archive),str(unpacked)],check=True,capture_output=True,timeout=180)
            else:
                with zipfile.ZipFile(archive) as bundle:bundle.extractall(filesystem_path(unpacked))
            self.prepared=validate_app(Path(filesystem_path(unpacked/top)),self.available['version'])
            self._state(status='prepared',progress=100,message='Package verified. Install when you are ready.')
        except Exception as exc:
            logging.exception('Desktop update download or package verification failed')
            self._state(status='error',message=str(exc) if isinstance(exc,ValueError) else 'Download or package verification failed. The installed app was not changed. See desktop.log for details.')
        return self.update_state()

    def cancel_update(self):
        self.cancel_event.set()
        if self.update_state()['status']=='waiting':self._state(status='prepared',message='Installation cancelled. Normal studio work continues.')
        return self.update_state()

    def _busy(self):
        if not self.app:raise ValueError('Close the separate browser/server studio and relaunch this desktop app before installing updates.')
        store=self.app.extensions['studio_store']
        live=self.app.extensions.get('live_instances',{}).get('studio')
        if live and (live.snapshot()['running'] or live.snapshot()['processing']):return True
        return (any(j['status'] in ('queued','running') for j in store.jobs())
            or any(e['status'] in ('preparing','rendering') for e in self.app.extensions['studio_planner'].entries())
            or any(r['status'] in ('queued','running') for r in self.app.extensions['studio_agent'].snapshot()['requests']))

    def install_update(self):
        if self.update_state()['status']=='waiting':return self.update_state()
        if not self.prepared:raise ValueError('Download and verify an update first.')
        if not getattr(sys,'frozen',False):raise ValueError('Install updates from the packaged desktop application.')
        target=application_root()
        if DATA.resolve().is_relative_to(target) or EXPORTS.resolve().is_relative_to(target):raise ValueError('Move saved data outside the installed app before updating.')
        self._busy();self.cancel_event.clear();self._state(status='waiting',message='Waiting for active batches and exports to finish. New requests are still retained.')
        threading.Thread(target=self._wait_install,args=(target,),daemon=True).start()
        return self.update_state()

    def restore_previous(self):
        if self.update_state()['status'] in ('downloading','installing','waiting'):raise ValueError('Finish or cancel the current update first.')
        target=application_root()
        for path in sorted((self.cache/'Recovery').glob('*/install-plan.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            plan=json.loads(path.read_text(encoding='utf-8'))
            from .update_install import validate_plan
            validate_plan(plan)
            old=Path(plan['previous'])
            if Path(plan['target']).resolve()!=target or not old.is_dir():continue
            manifest=old/('Contents/Resources/resources/desktop-release.json' if sys.platform=='darwin' else '_internal/resources/desktop-release.json')
            info=json.loads(manifest.read_text(encoding='utf-8'));self.prepared=validate_app(old,info['version'])
            self.available=dict(version=info['version'])
            return self.install_update()
        raise ValueError('No compatible previous app is available. Current readings and history are unchanged.')

    def _wait_install(self,target):
        try:
            while not self.cancel_event.wait(1):
                with operations.LOCK:
                    if self._busy():continue
                    operations.installing=True
                    try:self._launch_installer(target)
                    except Exception:operations.installing=False;raise
                    break
        except Exception as exc:self._state(status='error',message=str(exc) if isinstance(exc,ValueError) else 'Installation could not start; the existing app is unchanged.')

    def _launch_installer(self,target):
        from .update_install import launch
        recovery=self.cache/'Recovery'/uuid.uuid4().hex;recovery.mkdir(parents=True)
        source=self.app.extensions['studio_store'].path
        with sqlite3.connect(source) as database,sqlite3.connect(recovery/'history.sqlite3') as backup:
            if database.execute('PRAGMA user_version').fetchone()[0]>1:raise ValueError('This history schema requires a newer updater.')
            database.backup(backup)
        receipt=recovery/'health.json'
        plan=dict(target=str(target),prepared=str(self.prepared),pid=os.getpid(),health=str(receipt),version=self.available['version'],
                  data=str(DATA.resolve()),exports=str(EXPORTS.resolve()),workspace=str(self.workspace.resolve()) if self.workspace else None,
                  recovery=str(recovery),host=sys.platform)
        launch(plan,recovery)
        self._state(status='installing',message='Installing verified update and relaunching. History and exchange remain in place.')
        self.window.confirm_close=False;self.window.destroy()


class DesktopBridge:
    """Expose only update commands, never the Flask app, database, or keyring."""
    def __init__(self,updates):self._updates=updates
    def update_state(self):return self._updates.update_state()
    def check_update(self):return self._updates.check_update()
    def download_update(self):return self._updates.download_update()
    def cancel_update(self):return self._updates.cancel_update()
    def install_update(self):return self._updates.install_update()
    def restore_previous(self):return self._updates.restore_previous()
    def save_update_token(self,token):return self._updates.save_update_token(token)

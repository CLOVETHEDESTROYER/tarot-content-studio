"""Checked sibling staging + detached system installer, retaining the old app."""
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from .config import ROOT
from .audio import HIDDEN
from .updates import APP


def validate_plan(plan):
    target=Path(plan['target']).resolve();staged=Path(plan['staged']).resolve();previous=Path(plan['previous']).resolve()
    expected=APP+('.app' if plan['host']=='darwin' else '')
    if target.name!=expected or target.parent==target:raise ValueError('Unexpected installation target.')
    for path,prefix in ((staged,'.starpower-incoming-'),(previous,'.starpower-previous-')):
        if path.parent!=target.parent or not path.name.startswith(prefix):raise ValueError('Installer staging must be a checked sibling of the app.')
    for key in ('data','exports','health','recovery'):
        value=Path(plan[key]).resolve()
        if value==target or value.is_relative_to(target):raise ValueError('User data and recovery files must be outside the installed app.')
    if type(plan['pid']) is not int or plan['pid']<=0:raise ValueError('Invalid application process.')
    return plan


def launch(plan,recovery):
    parent=Path(plan['target']).parent
    if not os.access(parent,os.W_OK):raise ValueError('The app folder is not writable. Move the app to a writable Applications folder or install manually.')
    nonce=uuid.uuid4().hex
    plan.update(staged=str(parent/('.starpower-incoming-'+nonce)),previous=str(parent/('.starpower-previous-'+nonce)))
    validate_plan(plan)
    shutil.copytree(plan['prepared'],plan['staged'],symlinks=True)
    path=recovery/'install-plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
    env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'}
    for key in list(env):
        if key.startswith('_PYI_'):env.pop(key)
    if sys.platform=='darwin':
        script=recovery/'install.sh';shutil.copyfile(ROOT/'resources/install-update.sh',script)
        # Fixed positional arguments avoid generated shell commands and quoting issues.
        args=[plan[k] for k in ('target','staged','previous','health','version','data','exports')]
        subprocess.Popen(['/bin/bash',str(script),str(plan['pid']),*args],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    else:
        script=recovery/'install.ps1';shutil.copyfile(ROOT/'resources/install-update.ps1',script)
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-Plan',str(path)],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**HIDDEN)

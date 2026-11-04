"""Run offline and native-window checks on the executable that will ship."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
mac=sys.platform=='darwin'
app=ROOT/'desktop-dist'/('StarPower Content Studio.app' if mac else 'StarPower Content Studio')
exe=app/('Contents/MacOS/StarPower Content Studio' if mac else 'StarPower Content Studio.exe')
with tempfile.TemporaryDirectory(prefix='starpower-frozen-') as temporary:
    folder=Path(temporary);env={**os.environ,'STUDIO_DATA_DIR':str(folder/'data'),'STUDIO_EXPORT_DIR':str(folder/'exports'),
        'STUDIO_PORT':'5059','PYINSTALLER_RESET_ENVIRONMENT':'1'}
    offline=folder/'offline.json'
    subprocess.run([str(exe),'--self-test','--report',str(offline)],env=env,check=True,timeout=240)
    result=json.loads(offline.read_text());assert result['passed'];print(json.dumps(result))
    receipt=folder/'health.json'
    proc=subprocess.Popen([str(exe),'--gui-smoke','--update-health',str(receipt)],env=env)
    try:
        deadline=time.monotonic()+120
        while not receipt.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.5)
        if not receipt.exists():
            log=folder/'logs/desktop.log'
            raise RuntimeError(log.read_text() if log.exists() else 'Native window did not confirm startup.')
        health=json.loads(receipt.read_text());assert health['passed'] and health['nativeWindow']
        proc.wait(timeout=30);assert proc.returncode==0;print(json.dumps(health))
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=15)

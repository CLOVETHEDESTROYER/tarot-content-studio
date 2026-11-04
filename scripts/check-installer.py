"""Exercise real detached installers on disposable apps, never user data."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
mac=sys.platform=='darwin';APP='StarPower Content Studio'


def fixture(folder,mode):
    folder.mkdir(parents=True)
    (folder/'version.txt').write_text(mode)
    if mac:
        binary=folder/'Contents/MacOS'/APP;binary.parent.mkdir(parents=True)
        binary.write_text('''#!/bin/bash
mode="$(cat "$(dirname "$0")/../../version.txt")"
if [[ "$mode" == broken ]]; then exit 1; fi
if [[ "${1:-}" == --update-health ]]; then
  app="$(cd "$(dirname "$0")/../.." && pwd)"
  printf '{"passed":true,"version":"2.3.0","appPath":"%s"}' "$app" > "$2"
else
  echo "$mode" > "$STUDIO_DATA_DIR/relaunched.txt"
fi
sleep 2
''',encoding='utf-8');binary.chmod(0o755)
    else:
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        source=folder/'fixture.cs'
        source.write_text('''using System; using System.IO; using System.Threading;
class Fixture { static void Main(string[] args) {
 string app=AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
 string mode=File.ReadAllText(Path.Combine(app,"version.txt"));
 if(mode=="broken") Environment.Exit(1);
 if(args.Length>1 && args[0]=="--update-health") {
 string escaped=app.Replace("\\\\","\\\\\\\\").Replace("\\\"","\\\\\\\"");
 File.WriteAllText(args[1],"{\\\"passed\\\":true,\\\"version\\\":\\\"2.3.0\\\",\\\"appPath\\\":\\\""+escaped+"\\\"}");
 } else File.WriteAllText(Path.Combine(Environment.GetEnvironmentVariable("STUDIO_DATA_DIR"),"relaunched.txt"),mode);
 Thread.Sleep(2000);
} }''',encoding='utf-8')
        subprocess.run([str(compiler),'/nologo','/target:winexe','/out:'+str(folder/(APP+'.exe')),str(source)],check=True,capture_output=True)


def check(mode):
    with tempfile.TemporaryDirectory(prefix='starpower-installer-') as tmp:
        root=Path(tmp);target=root/(APP+('.app' if mac else ''));incoming=root/'.starpower-incoming-test'
        previous=root/'.starpower-previous-test';data=root/'data';data.mkdir();exports=root/'exports';exports.mkdir()
        recovery=root/'recovery';recovery.mkdir();health=recovery/'health.json'
        fixture(target,'old');fixture(incoming,mode)
        db=data/'studio.sqlite3'
        with sqlite3.connect(db) as c:c.execute('CREATE TABLE publication (id TEXT)');c.execute("INSERT INTO publication VALUES ('keep-latest')")
        c.close()
        exchange=root/'Tarot Exchange';exchange.mkdir();(exchange/'config.json').write_text('{"timezone":"America/Denver","requestId":"do-not-replay"}')
        before=(exchange/'config.json').read_bytes()
        if mac:
            command=['/bin/bash',str(ROOT/'resources/install-update.sh'),'99999999',str(target),str(incoming),str(previous),str(health),'2.3.0',str(data),str(exports)]
        else:
            plan=dict(target=str(target),staged=str(incoming),previous=str(previous),pid=99999999,health=str(health),version='2.3.0',data=str(data),exports=str(exports),recovery=str(recovery))
            path=recovery/'plan.json';path.write_text(json.dumps(plan))
            command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'resources/install-update.ps1'),'-Plan',str(path)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=25)
        time.sleep(3) # Disposable fixture executables release their files before cleanup.
        message=(recovery/'result.txt').read_text()
        expected='old' if mode=='broken' else mode
        assert (target/'version.txt').read_text()==expected,(message,result.stderr)
        assert ('Rolled back' if mode=='broken' else 'Update installed') in message,(message,result.stderr)
        if mode=='broken':assert (data/'relaunched.txt').read_text().strip()=='old'
        else:assert (previous/'version.txt').read_text()=='old'
        with sqlite3.connect(db) as c:assert c.execute('SELECT id FROM publication').fetchone()[0]=='keep-latest'
        c.close()
        assert (exchange/'config.json').read_bytes()==before
        print(json.dumps(dict(installer=sys.platform,scenario=mode,passed=True,latestHistoryPreserved=True,exchangePreserved=True)))


check('new');check('broken')

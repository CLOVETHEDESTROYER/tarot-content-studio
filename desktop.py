"""Native desktop entry point; no browser or terminal window is opened."""
import argparse
import json
import logging
import os
import sys
import threading
import urllib.request
from pathlib import Path


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--speech-worker':
        sys.argv=[sys.argv[0],*sys.argv[2:]]
        from studio.speech_worker import main as speak
        speak();return
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.workspace:
        workspace=args.workspace.resolve()
        if not (workspace/'data').is_dir():raise ValueError('The selected workspace has no data folder.')
        os.environ.setdefault('STUDIO_DATA_DIR',str(workspace/'data'))
        os.environ.setdefault('STUDIO_EXPORT_DIR',str(workspace/'exports'))
        from dotenv import load_dotenv
        load_dotenv(workspace/'.env')
    from studio.config import DATA,EXPORTS
    log_folder=DATA.parent/'logs' if getattr(sys,'frozen',False) else DATA/'logs'
    log_folder.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=log_folder/'desktop.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.self_test:
        from studio.desktop_smoke import verify
        result=verify()
        if args.report:args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
        return
    from app import create_app
    from waitress import create_server
    port=int(os.getenv('STUDIO_PORT','5057'));url=f'http://127.0.0.1:{port}'
    server=None;app=None
    try:
        with urllib.request.urlopen(url+'/api/config',timeout=1) as response:existing=json.load(response)
        if existing.get('application')!='starpower-content-studio':raise ValueError('Port is used by another app.')
        if Path(existing['export_folder']).resolve()!=EXPORTS.resolve():raise ValueError('Another studio workspace is already running on this port.')
    except (OSError,urllib.error.URLError):
        app=create_app();server=create_server(app,host='127.0.0.1',port=port,threads=8)
        threading.Thread(target=server.run,name='desktop-local-engine',daemon=True).start()
    import webview
    webview.settings['ALLOW_DOWNLOADS']=True
    webview.settings['ALLOW_FILE_URLS']=False
    debug_port=os.getenv('STUDIO_DESKTOP_DEBUG_PORT')
    if debug_port:webview.settings['REMOTE_DEBUGGING_PORT']=int(debug_port)
    window=webview.create_window('StarPower Content Studio',url,width=1450,height=940,min_size=(900,650),background_color='#103b28',text_select=True,confirm_close=True)
    def closing():
        if app:
            store=app.extensions['studio_store']
            active=any(j['status'] in ('queued','running') for j in store.jobs())
            active=active or any(r['status'] in ('queued','running') for r in app.extensions['studio_agent'].snapshot()['requests'])
            if active:
                if sys.platform=='win32':
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(None,'A batch or export is still running. Let it finish before closing the studio.','StarPower Content Studio',64)
                return False
    window.events.closing+=closing
    try:webview.start(gui='edgechromium' if sys.platform=='win32' else None,private_mode=False,storage_path=str(DATA/'desktop-profile'))
    finally:
        if app:
            app.extensions['studio_planner']._stop.set();app.extensions['studio_agent']._stop.set()
            for name in ('studio_agent','studio_planner','studio_jobs'):app.extensions[name].pool.shutdown(wait=False,cancel_futures=True)
        if server:server.close()


if __name__=='__main__':
    speech_worker=len(sys.argv)>1 and sys.argv[1]=='--speech-worker'
    try:main()
    except Exception as exc:
        if speech_worker:raise SystemExit(1)
        logging.exception('Desktop startup failed')
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'The studio could not start. See desktop.log in your studio data/log folder.\n\n'+str(exc)[:300],'StarPower Content Studio',16)
        raise

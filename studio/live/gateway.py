"""Read-only broadcast service; never expose the editor or host controls."""
import base64
import io
import os
from pathlib import Path
from flask import Flask,abort,jsonify,render_template,request,send_file,send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from ..config import ROOT,DATA
from ..engine import deck
from ..daily_visuals import visual_path
from .live_studio import LiveStudio
from .live_auth import register_live_auth


def create_gateway(folder=None):
    folder=Path(folder or DATA);resources=ROOT/'resources/live'
    app=Flask(__name__,static_folder=None,template_folder=str(resources/'templates'))
    app.config.update(SECRET_KEY=os.getenv('LIVE_SESSION_SECRET') or (folder/'live-session.key').read_text().strip(),LIVE_PUBLIC=True,LIVE_GATEWAY_MODE=True,
                      LIVE_AUTH_DB=str(folder/'live-auth.sqlite3'))
    from ..backgrounds import register_routes
    register_routes(app)
    app.wsgi_app=ProxyFix(app.wsgi_app,x_proto=1)
    @app.before_request
    def boundary():
        allowed=request.method=='GET' and request.path in ('/live/overlay','/health','/api/live/state')
        allowed|=request.method=='GET' and request.path.startswith(('/api/backgrounds/','/static/','/cards/','/api/artwork/','/api/daily/artwork/','/api/live/audio/'))
        allowed|=request.method=='POST' and request.path=='/api/live/overlay-access'
        if not allowed or (request.path=='/api/live/state' and request.args.get('public')!='1'):abort(404)
    auth=register_live_auth(app);storage=LiveStudio(folder/'live-studio.sqlite3',None)
    @app.get('/health')
    def health():return jsonify(ok=True)
    @app.get('/live/overlay')
    def overlay():return render_template('live_overlay.html')
    @app.get('/api/live/state')
    def state():
        auth['require_broadcast']();return jsonify(storage.snapshot(public=True))
    @app.get('/api/live/audio/<key>')
    def audio(key):
        auth['require_broadcast']();value=storage.audio(key)
        if not value:abort(404)
        header,encoded=value.split(',',1)
        return send_file(io.BytesIO(base64.b64decode(encoded)),mimetype='audio/wav' if 'wav' in header else 'audio/mpeg')
    @app.get('/cards/<card_id>')
    @app.get('/api/artwork/<deck_key>/<card_id>')
    def card(card_id,deck_key=None):
        selected=next((c for c in deck(deck_key or request.args.get('deck','celebrity')) if c.id==card_id),None)
        if not selected:abort(404)
        return send_file(selected.visual_path)
    @app.get('/api/daily/artwork/<style>/<family>/<key>')
    def daily_card(style,family,key):
        try:return send_file(visual_path(style,family,key))
        except (ValueError,KeyError):abort(404)
    @app.get('/static/<path:name>')
    def static(name):
        if name not in ('live.css','live-collab.css','live-cinema.css','live-overlay.js') and not (name.startswith(('brand/','fonts/','img/')) and Path(name).suffix.lower() in ('.png','.jpg','.jpeg','.woff2','.ttf')):abort(404)
        return send_from_directory(resources/'static',name)
    return app

import base64
import io
import os
import threading
from pathlib import Path

from flask import abort, jsonify, redirect, render_template, request, send_file
from urllib.parse import urlsplit

from .live_auth import register_live_auth
from .live_studio import LiveStudio, TikTokChat
from ..deck_catalog import deck_options


def register_live_routes(app, generate):
    app.config.setdefault('LIVE_STUDIO_DB',os.getenv('LIVE_STUDIO_DB',str(Path(app.root_path)/'data/live-studio.sqlite3')))
    instances = {}
    lock = threading.Lock()
    auth = register_live_auth(app)

    @app.before_request
    def live_hosting_boundary():
        if os.getenv('VERCEL') and request.path.startswith(('/live', '/api/live')):
            backend = os.getenv('LIVE_BACKEND_URL', '').rstrip('/')
            parsed = urlsplit(backend)
            if request.method == 'GET' and request.path.startswith('/live') and parsed.scheme == 'https' and parsed.netloc and not parsed.query and not parsed.fragment and parsed.path in ('', '/'):
                return redirect(backend + request.path)
            abort(503, 'Live Studio needs its always-on backend. Configure LIVE_BACKEND_URL after deploying it.')

    def studio():
        with lock:
            if not instances:
                path = Path(app.config['LIVE_STUDIO_DB'])
                instances['studio'] = LiveStudio(path, generate)
                instances['chat'] = TikTokChat(instances['studio'])
                with instances['studio'].transaction() as state:
                    if state['processing']:
                        state['queue'].insert(0, state['processing']['request'])
                        state['processing'] = None
                        state['paused'] = True
                        state['last_error'] = 'Interrupted reading restored to queue. Review it and resume.'
                if instances['studio'].snapshot()['running']:
                    instances['studio'].ensure_worker()
        return instances['studio']

    @app.get('/live')
    def live_admin():
        denied = auth['require_host']()
        if denied:
            return denied
        return render_template('live.html', gateway_url=app.config.get('BROADCAST_GATEWAY_URL',''),desktop_mode=app.config.get('LIVE_DESKTOP',False),live_csrf=auth['csrf_token'](), overlay_url=auth['overlay_url'](),
                               deck_options=deck_options(__import__('studio.config',fromlist=['ROOT']).ROOT))

    @app.get('/live/overlay')
    def live_overlay():
        if not app.config['LIVE_PUBLIC'] and request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403)
        return render_template('live_overlay.html')

    @app.get('/api/live/state')
    def live_state():
        if request.args.get('public') == '1':
            auth['require_broadcast']()
        else:
            denied = auth['require_host']()
            if denied:
                return denied
        state = studio().snapshot(public=request.args.get('public') == '1')
        if request.args.get('public') != '1':
            state['chat'] = dict(instances['chat'].status)
            state['overlay_url'] = auth['overlay_url']()
        response = jsonify(state)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/live/<action>')
    def live_action(action):
        denied = auth['require_host']()
        if denied:
            return denied
        if action == 'rotate-overlay':
            auth['rotate_overlay']()
            return jsonify(ok=True)
        engine = studio()
        data = request.get_json() or {}
        try:
            if action == 'settings':
                engine.settings(data)
            elif action == 'start':
                engine.start()
            elif action == 'pause':
                engine.pause()
            elif action == 'end':
                engine.end()
                instances['chat'].disconnect()
            elif action == 'request':
                engine.add(data.get('viewer', ''), data.get('question', ''), reading_type=data.get('reading_type'), reading_date=data.get('reading_date'))
            elif action in ('approve', 'remove'):
                engine.request_action(data.get('id'), action)
            elif action == 'connect':
                if not engine.snapshot()['running']:
                    raise ValueError('Start a session before connecting TikTok chat.')
                instances['chat'].connect(data.get('handle', 'digitaldrug'))
            elif action == 'disconnect':
                instances['chat'].disconnect()
            else:
                abort(404)
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True)

    @app.get('/api/live/audio/<display_id>')
    def live_audio(display_id):
        auth['require_broadcast']()
        audio = studio().audio(display_id)
        if not audio:
            abort(404)
        header, encoded = audio.split(',', 1)
        mimetype = 'audio/wav' if header == 'data:audio/wav;base64' else 'audio/mpeg'
        return send_file(io.BytesIO(base64.b64decode(encoded)), mimetype=mimetype)

    app.extensions['live_instances'] = instances
    app.extensions['live_bootstrap'] = studio
    app.extensions['live_auth'] = auth

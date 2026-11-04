import io
import json
import logging
import os
import re
import secrets
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from studio.config import ROOT, DATA, EXPORTS, ASSETS
from studio.deck_catalog import deck_options
from studio.engine import create, edit, redraw, write_sections, deck
from studio.jobs import Jobs
from studio.render import render_frame
from studio.store import Store, Conflict
from studio.platform_support import voice_capabilities
from studio.version import VERSION
from studio import operations


def create_app(store=None, run_jobs=True):
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 100_000
    token = secrets.token_urlsafe(32)
    database = store or Store()
    worker = Jobs(database) if run_jobs else None
    from studio.planner import DailyPlanner
    planner=DailyPlanner(database,worker,start=run_jobs) if worker else None
    from studio.agent_jobs import AgentJobs
    agent=AgentJobs(database,planner,worker,start=run_jobs) if worker else None
    app.extensions.update(studio_store=database, studio_jobs=worker, studio_planner=planner,studio_agent=agent)

    @app.before_request
    def local_boundary():
        if operations.installing and request.method not in ('GET','HEAD','OPTIONS'):
            abort(503,'The studio is installing an update. Retry after relaunch.')
        if request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403, 'Content Studio runs only on this computer.')
        if request.host.split(':')[0] not in ('127.0.0.1', 'localhost', '[', ''):
            abort(403, 'Open the studio at http://127.0.0.1:5057.')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            if origin and (urlsplit(origin).hostname not in ('127.0.0.1', 'localhost') or urlsplit(origin).scheme != 'http'):
                abort(403, 'Requests must come from the local studio.')
            if not secrets.compare_digest(request.headers.get('X-Studio-Token', ''), token):
                abort(403, 'Refresh the studio before saving or generating a reading.')
            if not request.is_json:
                abort(415, 'Send a JSON request.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/') and not request.path.startswith('/api/artwork/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, Conflict):
            return jsonify(error=str(exc)), 409
        if isinstance(exc, KeyError):
            return jsonify(error=exc.args[0]), 404
        if isinstance(exc, (ValueError, TypeError)):
            return jsonify(error=str(exc)), 400
        from openai import OpenAIError
        if isinstance(exc, OpenAIError):
            return jsonify(error='OpenAI could not write this reading. Check your connection and API credits, or choose built-in writing.'), 502
        logging.exception('Studio request failed')
        return jsonify(error='The studio encountered a problem. Your saved readings are safe. Please retry.'), 500

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError('Send a JSON object.')
        return data

    def expected(data):
        value = data.get('revision')
        if type(value) is not int or value < 1:
            raise ValueError('A saved reading revision is required. Refresh and retry.')
        return value

    def check_revision(draft, data):
        if expected(data) != draft['revision']:
            raise Conflict('This reading changed in another window. Reopen it from the library.')

    @app.get('/api/config')
    def config():
        return jsonify(token=token, decks=deck_options(ROOT), openai=bool(os.getenv('OPENAI_API_KEY')),
                       **voice_capabilities(), application='starpower-content-studio', export_folder=str(EXPORTS), version=VERSION,
                       today=datetime.now(ZoneInfo('America/Denver')).date().isoformat())

    @app.post('/api/daily/context')
    def daily_context():
        from studio.daily import validate_daily_settings
        from studio.daily_context import build_context
        return jsonify(build_context(validate_daily_settings(body())))

    @app.get('/api/daily/cards')
    def daily_cards():
        from studio.daily_visuals import gallery
        return jsonify(cards=gallery(request.args.get('style','esoteric-minimal')))

    @app.get('/api/daily/artwork/<style>/<family>/<key>')
    def daily_artwork(style,family,key):
        from studio.daily_visuals import visual_path
        path=visual_path(style,family,key)
        if not path.is_file():abort(404,'This daily visual is still being prepared.')
        return send_file(path,max_age=86400)

    @app.get('/api/planner')
    def planner_state():
        if not planner:abort(503,'Daily planner unavailable.')
        return jsonify(planner.snapshot())

    @app.put('/api/planner')
    def planner_settings():
        if not planner:abort(503,'Daily planner unavailable.')
        planner.save(body());return jsonify(planner.snapshot())

    @app.post('/api/planner/prepare')
    def planner_prepare():
        if not planner:abort(503,'Daily planner unavailable.')
        data=body()
        if type(data.get('retry',False)) is not bool:raise ValueError('Retry must be true or false.')
        return jsonify(planner.prepare(data.get('date'),data.get('edition'),data.get('retry',False))),202

    def agent_worker():
        if not agent:abort(503,'Agent worker unavailable.')
        return agent

    @app.get('/api/agent')
    def agent_state():return jsonify(agent_worker().snapshot())

    @app.put('/api/agent')
    def agent_settings():
        agent_worker().save(body());return jsonify(agent.snapshot())

    @app.post('/api/agent/poll')
    def agent_poll():
        body();agent_worker().poll();return jsonify(agent.snapshot())

    @app.post('/api/agent/first-test')
    def agent_first_test():
        body();root=agent_worker().prepare_exchange()
        example=json.loads((root/'Examples/first-test.json').read_text(encoding='utf-8'))
        return jsonify(agent.submit(example)),202

    @app.post('/api/agent/requests')
    def agent_request():return jsonify(agent_worker().submit(body())),202

    @app.post('/api/agent/requests/<key>/resume')
    def agent_resume(key):
        body();worker=agent_worker();return jsonify(worker.submit(worker.get(key)['request'],retry=True)),202

    @app.get('/api/agent/requests/<key>')
    def agent_request_status(key):return jsonify(agent_worker().get(key))

    @app.get('/api/agent/requests/<key>/bundle')
    def agent_bundle(key):
        record=agent_worker().get(key)
        if record['status']!='complete':abort(409,'Wait for the whole request to complete before retrieving media.')
        from studio.agent_jobs import inside
        root=Path(record['exchangeRoot']);path=inside(root,root/record['archive'])
        if not path.is_file():abort(404,'The completed handoff was moved or removed. Restore it; replays do not regenerate media.')
        return send_file(path,as_attachment=True,download_name=record['id']+'.zip')

    @app.post('/api/agent/reports')
    def agent_report():return jsonify(agent_worker().report(body()))

    @app.get('/api/readings')
    def readings():
        return jsonify(readings=database.list(), jobs=database.jobs())

    @app.post('/api/readings')
    def new_reading():
        return jsonify(database.create(create(body()))), 201

    @app.get('/api/readings/<key>')
    def reading(key):
        return jsonify(database.get(key))

    @app.put('/api/readings/<key>')
    def save_reading(key):
        data = body(); original = database.get(key)
        check_revision(original, data)
        changed = edit(original, data)
        if changed == original:
            return jsonify(original)
        return jsonify(database.save(changed, expected(data)))

    @app.post('/api/readings/<key>/redraw')
    def redraw_card(key):
        data = body(); original = database.get(key)
        check_revision(original, data)
        return jsonify(database.save(redraw(original, data.get('index'), data.get('orientation')), expected(data)))

    @app.post('/api/readings/<key>/rewrite')
    def rewrite_reading(key):
        data = body(); original = database.get(key)
        check_revision(original, data)
        if original['settings'].get('daily'):
            from studio.daily import write_daily
            original['sections'],original['writing_source']=write_daily(original['cards'],original['settings'],original['context'])
        else:
            original['sections'], original['writing_source'] = write_sections(original['cards'], original['settings'], secrets.token_hex(16))
        return jsonify(database.save(original, expected(data)))

    @app.post('/api/readings/<key>/<kind>')
    def start_job(key, kind):
        if kind not in ('preview', 'export'):
            abort(404)
        data = body(); draft = database.get(key)
        check_revision(draft, data)
        if not worker:
            abort(503, 'Renderer unavailable.')
        return jsonify(worker.submit(draft, kind)), 202

    @app.get('/api/jobs/<key>')
    def job(key):
        return jsonify(database.get_job(key))

    @app.get('/api/artwork/<deck_key>/<card_id>')
    def artwork(deck_key, card_id):
        selected = next((c for c in deck(deck_key) if c.id == card_id), None)
        if not selected:
            abort(404)
        return send_file(selected.image_path, max_age=86400)

    def prepared(key):
        if not re.fullmatch('[a-f0-9]{64}', key):
            abort(404)
        folder = DATA / 'prepared' / key
        if not (folder / 'manifest.json').is_file():
            abort(404, 'Prepare a preview first.')
        return folder

    @app.get('/api/previews/<key>/manifest')
    def manifest(key):
        return send_file(prepared(key) / 'manifest.json', mimetype='application/json')

    @app.get('/api/previews/<key>/audio')
    def audio(key):
        return send_file(prepared(key) / 'narration.wav', mimetype='audio/wav', conditional=True)

    @app.get('/api/previews/<key>/frame')
    def frame(key):
        folder = prepared(key)
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        draft = json.loads((folder / 'reading.json').read_text(encoding='utf-8'))
        t = float(request.args.get('t', 0))
        if not 0 <= t <= 600:
            raise ValueError('Choose a time inside the reading.')
        output = io.BytesIO()
        render_frame(draft, manifest, t, 360).save(output, format='JPEG', quality=88)
        output.seek(0)
        return send_file(output, mimetype='image/jpeg')

    @app.get('/api/poster/<key>')
    def poster(key):
        draft = database.get(key)
        simple = {'duration': 1, 'sections': [{'key': 'hook', 'card_id': None, 'start': 0, 'end': 1}],
                  'captions': [{'start':0, 'end':1, 'text': draft['sections'][0]['text'].split('.')[0] + '.'}]}
        output = io.BytesIO(); render_frame(draft, simple, 0, 360).save(output, format='JPEG', quality=90); output.seek(0)
        return send_file(output, mimetype='image/jpeg')

    @app.get('/api/exports/<key>/<name>')
    def download(key, name):
        export = database.get_job(key)
        if export['kind'] != 'export' or export['status'] != 'done' or name not in export.get('files', []):
            abort(404, 'This export is not ready.')
        return send_file(EXPORTS / key / name, as_attachment=request.args.get('download') == '1',
                         download_name=f"starpower-{key[:8]}-{name}", conditional=True)

    @app.get('/assets/<path:name>')
    def assets(name):
        return send_from_directory(ASSETS, name, max_age=86400)

    @app.get('/')
    @app.get('/<path:name>')
    def frontend(name='index.html'):
        distribution = ROOT / 'frontend' / 'dist'
        path = distribution / name
        if path.is_file() and path.resolve().is_relative_to(distribution.resolve()):
            return send_from_directory(distribution, name)
        if name.startswith('api/'):
            abort(404)
        return send_from_directory(distribution, 'index.html')

    return app


if __name__ == '__main__':
    from waitress import serve
    port = int(os.getenv('STUDIO_PORT', '5057'))
    print(f'StarPower Content Studio: http://127.0.0.1:{port}', flush=True)
    serve(create_app(), host='127.0.0.1', port=port, threads=8)

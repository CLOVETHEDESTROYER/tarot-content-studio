"""Host login and a separate, revocable read-only broadcast capability."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash


def register_live_auth(app):
    if not app.secret_key:
        app.secret_key = os.getenv('LIVE_SESSION_SECRET')
    app.config.setdefault('LIVE_USERNAME', os.getenv('LIVE_USERNAME', ''))
    app.config.setdefault('LIVE_PASSWORD_HASH', os.getenv('LIVE_PASSWORD_HASH', ''))
    app.config.setdefault('LIVE_PUBLIC', os.getenv('LIVE_PUBLIC') == '1')
    app.config.setdefault('LIVE_AUTH_DB', os.getenv('LIVE_AUTH_DB', str(Path(app.root_path) / 'data/live-auth.sqlite3')))
    app.config.update(SESSION_COOKIE_NAME='starpower_host', SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=app.config['LIVE_PUBLIC'],
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24))

    def desktop_local():
        return app.config.get('LIVE_DESKTOP') and os.getenv('LIVE_REQUIRE_LOGIN')!='1' and request.remote_addr in ('127.0.0.1','::1')

    def configured():
        if app.config.get('LIVE_GATEWAY_MODE'):return bool(app.secret_key and len(app.secret_key)>=32)
        return bool(app.secret_key and len(app.secret_key) >= 32 and app.config['LIVE_USERNAME']
                    and app.config['LIVE_PASSWORD_HASH'])

    def fingerprint():
        return hashlib.sha256(app.config['LIVE_PASSWORD_HASH'].encode()).hexdigest()

    def host_logged_in():
        return configured() and session.get('live_host') == fingerprint()

    def csrf_token():
        if 'live_csrf' not in session:
            session['live_csrf'] = secrets.token_urlsafe(32)
        return session['live_csrf']

    def check_csrf(value):
        if not value or not hmac.compare_digest(str(value), session.get('live_csrf', '')):
            abort(403, 'Session verification failed. Reload the dashboard and try again.')

    def check_origin():
        if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
            abort(403)

    def access_location():
        if not app.config['LIVE_PUBLIC'] and request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403, 'Remote Live Studio access is not enabled.')
        if app.config['LIVE_PUBLIC'] and not request.is_secure and not app.testing:
            abort(403, 'Live Studio requires HTTPS.')

    def require_host():
        access_location()
        if desktop_local():
            if request.method=='POST':
                check_origin()
                if not request.is_json:abort(415)
                check_csrf(request.headers.get('X-Live-CSRF'))
            return None
        if not configured():
            abort(503, 'Live Studio login is not configured. Set the LIVE authentication environment variables.')
        if not host_logged_in():
            if request.path.startswith('/api/'):
                abort(401, 'Sign in to Live Studio.')
            return redirect(url_for('live_login'))
        if request.method == 'POST':
            check_origin()
            if not request.is_json:
                abort(415)
            check_csrf(request.headers.get('X-Live-CSRF'))
        return None

    def auth_db():
        path = Path(app.config['LIVE_AUTH_DB'])
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=15)
        db.execute('CREATE TABLE IF NOT EXISTS auth_attempts (scope TEXT PRIMARY KEY, failures INTEGER, expires REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS broadcast_access (id INTEGER PRIMARY KEY, token TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO broadcast_access VALUES (1, ?)', (secrets.token_urlsafe(32),))
        db.commit()
        return db

    def overlay_token():
        with closing(auth_db()) as db:
            return db.execute('SELECT token FROM broadcast_access WHERE id=1').fetchone()[0]

    def rotate_overlay():
        with closing(auth_db()) as db:
            db.execute('UPDATE broadcast_access SET token=? WHERE id=1', (secrets.token_urlsafe(32),))
            db.commit()

    def broadcast_allowed():
        if desktop_local() or host_logged_in():
            return True
        if not configured():
            return False
        ticket = request.headers.get('X-Broadcast-Ticket') or request.args.get('ticket')
        if ticket:
            try:
                value = URLSafeTimedSerializer(app.secret_key, salt='live-broadcast-link').loads(ticket, max_age=12 * 3600)
                return isinstance(value, str) and hmac.compare_digest(value, hashlib.sha256(overlay_token().encode()).hexdigest())
            except (BadSignature, SignatureExpired):
                return False
        try:
            token_hash = URLSafeTimedSerializer(app.secret_key, salt='live-broadcast').loads(
                request.cookies.get('starpower_broadcast', ''), max_age=12 * 3600)
            return hmac.compare_digest(token_hash, hashlib.sha256(overlay_token().encode()).hexdigest())
        except (BadSignature, SignatureExpired):
            return False

    def require_broadcast():
        access_location()
        if not broadcast_allowed():
            abort(401, 'Open the private broadcast link from Live Studio.')

    def overlay_url():
        # A short-lived read-only ticket also works when embedded browsers block cookies.
        ticket = URLSafeTimedSerializer(app.secret_key, salt='live-broadcast-link').dumps(
            hashlib.sha256(overlay_token().encode()).hexdigest())
        base = os.getenv('LIVE_BROADCAST_URL', '').rstrip('/')
        if not base:
            try:
                base = json.loads((Path(app.config.get('LIVE_DATA_DIR',str(Path(app.root_path)/'data'))) / 'broadcast-test.json').read_text(encoding='utf-8-sig'))['url'].rstrip('/')
            except (OSError, ValueError, KeyError, TypeError):
                base = ''
        parsed = urlsplit(base)
        if base and parsed.scheme == 'https' and parsed.netloc and parsed.path in ('', '/') and not parsed.query and not parsed.fragment:
            return base + '/live/overlay?ticket=' + ticket
        return url_for('live_overlay', _external=True) + '?ticket=' + ticket

    @app.route('/live/login', methods=['GET', 'POST'])
    def live_login():
        access_location()
        if not configured():
            return render_template('live_login.html', configured=False), 503
        if host_logged_in():
            return redirect(url_for('live_admin'))
        error = None
        if request.method == 'POST':
            check_origin()
            check_csrf(request.form.get('csrf'))
            scope = hmac.new(str(app.secret_key).encode(), (request.remote_addr or '').encode(), hashlib.sha256).hexdigest()
            now = time.time()
            with closing(auth_db()) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM auth_attempts WHERE expires < ?', (now,))
                attempt = db.execute('SELECT failures FROM auth_attempts WHERE scope=?', (scope,)).fetchone()
                if attempt and attempt[0] >= 5:
                    db.commit()
                    return render_template('live_login.html', configured=True, csrf=csrf_token(),
                                           error='Too many attempts. Please wait five minutes.'), 429
                password_ok = check_password_hash(app.config['LIVE_PASSWORD_HASH'] or dummy_hash,
                                                  request.form.get('password', '')[:1024])
                username_ok = hmac.compare_digest(request.form.get('username', '').encode(),
                                                  app.config['LIVE_USERNAME'].encode())
                if username_ok and password_ok:
                    db.execute('DELETE FROM auth_attempts WHERE scope=?', (scope,))
                    db.commit()
                    session.clear()
                    session.permanent = True
                    session['live_host'] = fingerprint()
                    csrf_token()
                    return redirect(url_for('live_admin'))
                db.execute('INSERT INTO auth_attempts VALUES (?, 1, ?) ON CONFLICT(scope) DO UPDATE SET failures=failures+1',
                           (scope, now + 300))
                db.commit()
            error = 'Username or password is incorrect.'
        return render_template('live_login.html', configured=True, csrf=csrf_token(), error=error), 401 if error else 200

    @app.post('/live/logout')
    def live_logout():
        access_location()
        check_origin()
        check_csrf(request.form.get('csrf'))
        session.clear()
        return redirect(url_for('live_login'))

    @app.post('/api/live/overlay-access')
    def live_overlay_access():
        access_location()
        check_origin()
        if not configured():
            abort(503)
        supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
        if not supplied or not hmac.compare_digest(supplied, overlay_token()):
            abort(401)
        signed = URLSafeTimedSerializer(app.secret_key, salt='live-broadcast').dumps(
            hashlib.sha256(supplied.encode()).hexdigest())
        response = jsonify(ok=True)
        response.set_cookie('starpower_broadcast', signed, max_age=12 * 3600, httponly=True,
                            secure=app.config['LIVE_PUBLIC'], samesite='Lax')
        return response

    @app.after_request
    def live_private_headers(response):
        if request.path.startswith(('/live', '/api/live')):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'same-origin' if request.path in ('/live', '/live/login', '/live/logout') else 'no-referrer'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    return dict(require_host=require_host, require_broadcast=require_broadcast, csrf_token=csrf_token,
                overlay_url=overlay_url, rotate_overlay=rotate_overlay, configured=configured)

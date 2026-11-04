import hashlib
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from flask import Flask
from werkzeug.security import generate_password_hash

from studio.live.live_routes import register_live_routes
from studio.live.live_studio import LiveStudio


class LiveAuthTests(unittest.TestCase):
    password_hash = generate_password_hash('test-password')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict('os.environ', {'LIVE_STUDIO_DB': str(Path(self.temp.name) / 'studio.sqlite3')})
        self.env.start()
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'resources/live/templates'))
        self.app.config.update(TESTING=True, SECRET_KEY='test-session-secret-with-at-least-32-characters',
                               LIVE_USERNAME='TestHost', LIVE_PASSWORD_HASH=self.password_hash,
                               LIVE_STUDIO_DB=str(Path(self.temp.name)/'routes.sqlite3'), LIVE_AUTH_DB=str(Path(self.temp.name) / 'auth.sqlite3'), LIVE_PUBLIC=False)
        register_live_routes(self.app, lambda job: {})
        self.client = self.app.test_client()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def login(self, client=None, username='TestHost', password='test-password'):
        client = client or self.client
        client.get('/live/login')
        with client.session_transaction() as session:
            csrf = session['live_csrf']
        return client.post('/live/login', data=dict(username=username, password=password, csrf=csrf))

    def csrf(self):
        with self.client.session_transaction() as session:
            return {'X-Live-CSRF': session['live_csrf']}

    def test_private_tools_require_login(self):
        self.assertEqual(self.client.get('/live').status_code, 302)
        self.assertEqual(self.client.get('/api/live/state').status_code, 401)
        self.assertEqual(self.client.get('/api/live/state?public=1').status_code, 401)
        self.assertEqual(self.client.post('/api/live/start', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/live/audio/no-id').status_code, 401)

    def test_case_sensitive_login_and_logout(self):
        self.assertEqual(self.login(username='testhost').status_code, 401)
        self.assertEqual(self.login().status_code, 302)
        response = self.client.get('/live')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'test-password', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
        csrf = self.csrf()['X-Live-CSRF']
        self.assertEqual(self.client.post('/live/logout', data={'csrf': csrf}).status_code, 302)
        self.assertEqual(self.client.get('/api/live/state').status_code, 401)

    def test_csrf_and_origin(self):
        self.assertEqual(self.client.post('/live/login', data={}).status_code, 403)
        self.login()
        self.assertEqual(self.client.post('/api/live/settings', json={'interval': 90}).status_code, 403)
        self.assertEqual(self.client.post('/api/live/settings', json={'interval': 90}, headers={**self.csrf(), 'Origin':'https://other.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/live/settings', json={'interval': 90}, headers=self.csrf()).status_code, 200)

    def test_login_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.login(password='wrong').status_code, 401)
        self.assertEqual(self.login().status_code, 429)

    def test_read_only_overlay_token_and_rotation(self):
        self.login()
        with patch.object(LiveStudio, 'ensure_worker'):
            state = self.client.get('/api/live/state').json
        ticket = parse_qs(urlsplit(state['overlay_url']).query)['ticket'][0]
        with closing(sqlite3.connect(self.app.config['LIVE_AUTH_DB'])) as db:
            key = db.execute('SELECT token FROM broadcast_access WHERE id=1').fetchone()[0]
        no_cookies = self.app.test_client(use_cookies=False)
        self.assertEqual(no_cookies.get('/api/live/state?public=1', headers={'X-Broadcast-Ticket': ticket}).status_code, 200)
        self.assertEqual(no_cookies.get('/api/live/state?public=1&ticket='+ticket).status_code, 200)
        self.assertEqual(no_cookies.get('/api/live/state?ticket='+ticket).status_code, 401)
        self.assertEqual(no_cookies.get('/api/live/state?public=1&ticket='+ticket+'bad').status_code, 401)
        with patch('time.time', return_value=__import__('time').time()+13*3600):
            self.assertEqual(no_cookies.get('/api/live/state?public=1&ticket='+ticket).status_code, 401)
        viewer = self.app.test_client()
        self.assertEqual(viewer.post('/api/live/overlay-access', headers={'Authorization':'Bearer wrong'}).status_code, 401)
        access = viewer.post('/api/live/overlay-access', headers={'Authorization':'Bearer '+key})
        self.assertEqual(access.status_code, 200)
        self.assertIn('HttpOnly', access.headers['Set-Cookie'])
        public = viewer.get('/api/live/state?public=1')
        self.assertEqual(public.status_code, 200)
        self.assertNotIn('overlay_url', public.json)
        self.assertNotIn('chat', public.json)
        self.assertEqual(viewer.get('/api/live/state').status_code, 401)
        self.assertEqual(viewer.post('/api/live/start', json={}).status_code, 401)
        self.client.post('/api/live/rotate-overlay', json={}, headers=self.csrf())
        self.assertEqual(no_cookies.get('/api/live/state?public=1&ticket='+ticket).status_code, 401)
        self.assertEqual(viewer.get('/api/live/state?public=1').status_code, 401)
        self.assertEqual(viewer.post('/api/live/overlay-access', headers={'Authorization':'Bearer '+key}).status_code, 401)

    def test_password_rotation_invalidates_host_session(self):
        self.login()
        self.app.config['LIVE_PASSWORD_HASH'] = generate_password_hash('new-password')
        self.assertEqual(self.client.get('/api/live/state').status_code, 401)

    def test_missing_configuration_fails_closed(self):
        self.app.config['LIVE_PASSWORD_HASH'] = ''
        self.assertEqual(self.client.get('/live/login').status_code, 503)
        self.assertEqual(self.client.get('/api/live/state?public=1').status_code, 401)

    def test_hosted_https_and_vercel_redirect(self):
        self.app.config['LIVE_PUBLIC'] = True
        response = self.client.get('/live/login', base_url='https://live.example', environ_overrides={'REMOTE_ADDR':'203.0.113.10'})
        self.assertEqual(response.status_code, 200)
        with patch.dict('os.environ', {'VERCEL':'1', 'LIVE_BACKEND_URL':'https://live.example'}):
            self.assertEqual(self.client.get('/live').location, 'https://live.example/live')
            self.assertEqual(self.client.get('/live/overlay').location, 'https://live.example/live/overlay')
            self.assertEqual(self.client.get('/api/live/state').status_code, 503)
            self.assertEqual(self.client.post('/api/live/overlay-access').status_code, 503)

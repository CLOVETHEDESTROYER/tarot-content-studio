import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from .config import DATA


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, path=None):
        self.path = path or DATA / 'studio.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, updated TEXT NOT NULL, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, created TEXT NOT NULL, body TEXT NOT NULL)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return closing_connection(db)

    def create(self, draft):
        draft = {**draft, 'revision': 1, 'created': now(), 'updated': now()}
        with self.connect() as db:
            db.execute('INSERT INTO drafts VALUES (?, ?, ?, ?)', (draft['id'], 1, draft['updated'], json.dumps(draft)))
        return draft

    def get(self, key):
        with self.connect() as db:
            row = db.execute('SELECT body FROM drafts WHERE id=?', (key,)).fetchone()
        if row is None:
            raise KeyError('Reading not found.')
        return json.loads(row['body'])

    def save(self, draft, expected):
        draft = {**draft, 'revision': expected + 1, 'updated': now()}
        with self.connect() as db:
            result = db.execute('UPDATE drafts SET revision=?, updated=?, body=? WHERE id=? AND revision=?',
                                (draft['revision'], draft['updated'], json.dumps(draft), draft['id'], expected))
            if result.rowcount != 1:
                raise Conflict('This reading changed in another window. Reopen it from the library.')
        return draft

    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM drafts ORDER BY updated DESC LIMIT 200').fetchall()
        readings = [json.loads(row['body']) for row in rows]
        return [reading for reading in readings if not reading.get('archived', False)]

    def put_job(self, job):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?)',
                       (job['id'], job['draft_id'], job['created'], json.dumps(job)))
        return job

    def get_job(self, key):
        with self.connect() as db:
            row = db.execute('SELECT body FROM jobs WHERE id=?', (key,)).fetchone()
        if row is None:
            raise KeyError('Export not found.')
        return json.loads(row['body'])

    def jobs(self, draft_id=None):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM jobs ORDER BY created DESC LIMIT 200').fetchall()
        jobs = [json.loads(row['body']) for row in rows]
        return [j for j in jobs if draft_id is None or j['draft_id'] == draft_id]

    def recover(self):
        for job in self.jobs():
            if job['status'] in ('queued', 'running'):
                job.update(status='failed', error='Studio restarted before this export finished. Your saved reading is safe; export again.')
                self.put_job(job)
            elif job.get('duration') is not None and (not isinstance(job['duration'], (int,float)) or not math.isfinite(job['duration']) or not 1 <= job['duration'] <= 600):
                job.update(status='failed', error='This preview has an invalid duration. Rebuild it before exporting.')
                self.put_job(job)


class closing_connection:
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        return self.db
    def __exit__(self, kind, value, trace):
        try:
            self.db.rollback() if kind else self.db.commit()
        finally:
            self.db.close()

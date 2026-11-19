import json
import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    path = Path(os.getenv('DB_PATH', 'data/bairro.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, at TEXT, report_id TEXT, action TEXT, detail TEXT)')
        con.execute('CREATE TABLE IF NOT EXISTS photos (report_id TEXT PRIMARY KEY, mime TEXT NOT NULL, data BLOB NOT NULL, sha256 TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS report_requests (request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, report_id TEXT NOT NULL)')
        con.commit()
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def audit(con, report_id, action, detail=''):
    con.execute('INSERT INTO audit(at,report_id,action,detail) VALUES (?,?,?,?)',
                (now(), report_id, action, detail))


class IdempotencyConflict(ValueError):
    pass


def _read(c, row):
    report = json.loads(row['body'])
    photo = c.execute('SELECT sha256 FROM photos WHERE report_id=?', (report['id'],)).fetchone()
    report['image_available'] = photo is not None
    report['image_sha256'] = photo['sha256'] if photo else None
    report.setdefault('client_request_id', None)
    return report


def _existing(c, request_id, fingerprint):
    if not request_id:
        return None
    request = c.execute('SELECT * FROM report_requests WHERE request_id=?', (request_id,)).fetchone()
    if request:
        if request['fingerprint'] != fingerprint:
            raise IdempotencyConflict('Identificador de tentativa já usado com outros dados. Inicie um novo relato.')
        return _read(c, c.execute('SELECT body FROM reports WHERE id=?', (request['report_id'],)).fetchone())
    return None


def existing_request(request_id, fingerprint):
    with connection() as c:
        return _existing(c, request_id, fingerprint)


def insert(report, photo=None, fingerprint=None):
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        existing = _existing(c, report.get('client_request_id'), fingerprint)
        if existing:
            return existing
        report['image_available'] = photo is not None
        report['image_sha256'] = hashlib.sha256(photo).hexdigest() if photo else None
        c.execute('INSERT INTO reports VALUES (?,?)', (report['id'], json.dumps(report, ensure_ascii=False)))
        if photo:
            c.execute('INSERT INTO photos VALUES (?,?,?,?)', (report['id'], 'image/jpeg', photo, report['image_sha256']))
        if report.get('client_request_id'):
            c.execute('INSERT INTO report_requests VALUES (?,?,?)', (report['client_request_id'], fingerprint, report['id']))
        audit(c, report['id'], 'created')
    return report


def all_reports():
    with connection() as c:
        return [_read(c, r) for r in c.execute('SELECT body FROM reports ORDER BY rowid DESC').fetchall()]


def get(report_id):
    with connection() as c:
        row = c.execute('SELECT body FROM reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise KeyError(report_id)
        return _read(c, row)


def get_photo(report_id):
    with connection() as c:
        row = c.execute('SELECT mime,data,sha256 FROM photos WHERE report_id=?', (report_id,)).fetchone()
        if not row:
            raise KeyError(report_id)
        return dict(row)


def mutate(report_id, transform, action):
    # Transaction includes state check and write: concurrent clicks cannot create two protocols.
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT body FROM reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise KeyError(report_id)
        before = _read(c, row)
        after = transform(before)
        c.execute('UPDATE reports SET body=? WHERE id=?', (json.dumps(after, ensure_ascii=False), report_id))
        audit(c, report_id, action, after['status'])
        return after


def sound_event(event):
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT body FROM events WHERE id=?',(event['event_id'],)).fetchone()
        if row:
            existing=json.loads(row['body'])
            if existing != event:
                raise ValueError('Identificador já usado por outro evento.')
            return existing
        c.execute('INSERT INTO events VALUES (?,?)',(event['event_id'],json.dumps(event,ensure_ascii=False)))
    return event


def sound_events():
    with connection() as c:
        return [json.loads(r['body']) for r in c.execute('SELECT body FROM events ORDER BY rowid DESC')]


def analyzed_sound_event(event_id):
    """Resolve server-owned evidence; never trust scores sent with a report."""
    with connection() as c:
        row = c.execute('SELECT body FROM events WHERE id=?', (event_id,)).fetchone()
    if not row:
        raise ValueError('Análise sonora não encontrada. Analise o áudio antes de vinculá-lo ao relato.')
    event = json.loads(row['body'])
    if event.get('source') != 'yamnet' or (event.get('analysis') or {}).get('mode') != 'yamnet':
        raise ValueError('Vincule uma análise YAMNet executada pelo servidor; importações manuais não são aceitas aqui.')
    return event


def existing_audio_event(event_id, audio_sha256):
    with connection() as c:
        return _audio_event(c, event_id, audio_sha256)


def _audio_event(c, event_id, audio_sha256):
    row = c.execute('SELECT body FROM events WHERE id=?', (event_id,)).fetchone()
    if row:
        event = json.loads(row['body'])
        if event.get('source') != 'yamnet' or event.get('audio_sha256') != audio_sha256:
            raise IdempotencyConflict('Identificador de análise já usado com outro áudio. Inicie uma nova análise.')
        return event
    return None


def save_audio_event(event):
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        existing = _audio_event(c, event['event_id'], event['audio_sha256'])
        if existing:
            return existing
        c.execute('INSERT INTO events VALUES (?,?)', (event['event_id'], json.dumps(event, ensure_ascii=False)))
        audit(c, event['event_id'], 'audio_analysis', event['model_version'])
    return event

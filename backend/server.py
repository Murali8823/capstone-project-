"""ShieldPay LAN demonstration backend.

This phase uses deterministic receiver scores and simulated balances. Escrow
records are stored in SQLite only; Phase 4 will add actual local-EVM escrow.
The service intentionally uses Python's standard library (no pip dependencies).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Full, Queue
from threading import RLock, Thread
from urllib.parse import urlparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.environ.get('SHIELDPAY_DATABASE', str(ROOT / 'shieldpay.sqlite3')))
HOST = os.environ.get('SHIELDPAY_HOST', '0.0.0.0')
PORT = int(os.environ.get('SHIELDPAY_PORT', '8765'))
ESCROW_TIMEOUT_SECONDS = max(10, int(os.environ.get('SHIELDPAY_ESCROW_TIMEOUT_SECONDS', '300')))
ADMIN_SESSION_SECONDS = max(60, int(os.environ.get('SHIELDPAY_ADMIN_SESSION_SECONDS', '28800')))
ADMIN_PASSWORD = os.environ.get('SHIELDPAY_ADMIN_PASSWORD', 'shieldpay-admin')
ADMIN_TOKEN_SECRET = os.environ.get('SHIELDPAY_ADMIN_TOKEN_SECRET', 'local-demo-token-secret-change-me').encode()
CHAIN_CONFIG = ROOT / 'backend' / 'chain_config.json'
CHAIN_BRIDGE = ROOT / 'chain' / 'bridge.cjs'
DASHBOARD_FILE = ROOT / 'dashboard' / 'index.html'
DASHBOARD_SCRIPT = ROOT / 'dashboard' / 'dashboard.js'
LOCK = RLock()
SUBSCRIBERS: set[Queue] = set()
MAX_AMOUNT_PAISE = 100_000_000  # INR 1,000,000

SEED_USERS = (
    ('maya', 'Maya Shah', 'maya@shieldpay', 'sender', 1250000, '#e78368', 0),
    ('arjun', 'Arjun Rao', 'arjun@shieldpay', 'sender', 890000, '#6588d5', 0),
    ('riya', 'Riya Sen', 'riya@shieldpay', 'sender', 1530000, '#a271bf', 0),
    ('scammer', 'Suspicious Profile', 'watch@shieldpay', 'scammer', 0, '#d36565', 95),
    ('business', 'Northstar Gadgets', 'northstar@shieldpay', 'business', 0, '#20a7c7', 65),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE, timeout=10, isolation_level='DEFERRED')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_database() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, connect() as db:
        db.execute('PRAGMA journal_mode = WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, upi TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('sender','scammer','business')),
          balance_paise INTEGER NOT NULL CHECK(balance_paise >= 0),
          color TEXT NOT NULL, scam_score INTEGER NOT NULL CHECK(scam_score BETWEEN 0 AND 100)
        );
        CREATE TABLE IF NOT EXISTS transactions (
          id TEXT PRIMARY KEY, sender_id TEXT NOT NULL REFERENCES users(id),
          receiver_id TEXT NOT NULL REFERENCES users(id), amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
          score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100), status TEXT NOT NULL,
          reason TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          expires_at TEXT, scenario TEXT NOT NULL DEFAULT 'demo', blockchain_tx_hash TEXT,
          idempotency_key TEXT UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
        CREATE TABLE IF NOT EXISTS score_history (
          id TEXT PRIMARY KEY, receiver_id TEXT NOT NULL REFERENCES users(id),
          previous_score INTEGER NOT NULL, new_score INTEGER NOT NULL,
          changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, decision TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES users(id),
          receiver_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
          UNIQUE(reporter_id,receiver_id)
        );
        CREATE TABLE IF NOT EXISTS audit_events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
          event TEXT NOT NULL, transaction_id TEXT, payload TEXT NOT NULL,
          created_at TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS demo_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if count == 0:
            db.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?)', SEED_USERS)
        db.execute("INSERT OR IGNORE INTO demo_meta(key,value) VALUES('schema_version','1')")


def amount_to_paise(value: object) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Enter a valid amount.')
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Amount must be greater than zero.')
    if amount > Decimal('1000000'):
        raise ValueError('Amount must be at most ₹10,00,000.00.')
    quantized = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    paise = int(quantized * 100)
    if paise <= 0 or paise > MAX_AMOUNT_PAISE:
        raise ValueError('Amount must be at most ₹10,00,000.00.')
    return paise


def money(paise: int) -> float:
    return paise / 100


def user_json(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'], 'name': row['name'], 'upi': row['upi'],
        'role': row['role'], 'balance': money(row['balance_paise']),
        'color': row['color'], 'scam_score': row['scam_score'],
    }


def transaction_json(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'], 'sender_id': row['sender_id'], 'receiver_id': row['receiver_id'],
        'amount': money(row['amount_paise']), 'amount_paise': row['amount_paise'],
        'scam_score': row['score'], 'status': row['status'], 'reason': row['reason'],
        'created_at': row['created_at'], 'updated_at': row['updated_at'],
        'expires_at': row['expires_at'], 'scenario': row['scenario'],
        'blockchain_tx_hash': row['blockchain_tx_hash'],
        'escrow_backend_only': row['status'] in ('ESCROW', 'MANUAL_REVIEW') and not row['blockchain_tx_hash'],
    }


def chain_enabled() -> bool:
    return os.environ.get('SHIELDPAY_CHAIN_ENABLED', '1').lower() not in ('0', 'false', 'no') and CHAIN_CONFIG.exists()


def call_chain(action: str, payload: dict, timeout: int = 45) -> dict:
    """Ask the local ethers bridge to execute a Hardhat-chain operation."""
    try:
        result = subprocess.run(
            ['node', str(CHAIN_BRIDGE), action, json.dumps(payload, separators=(',', ':'))],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False,
            env={**os.environ, 'SHIELDPAY_CHAIN_RPC_URL': os.environ.get('SHIELDPAY_CHAIN_RPC_URL', 'http://127.0.0.1:8545')},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'Local blockchain bridge unavailable: {exc}') from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or 'Unknown chain error').strip()[-700:]
        raise RuntimeError(message)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Blockchain bridge returned invalid JSON.') from exc


def audit(db: sqlite3.Connection, event: str, payload: dict, transaction_id: str | None = None) -> dict:
    previous = db.execute('SELECT hash FROM audit_events ORDER BY sequence DESC LIMIT 1').fetchone()
    prev_hash = previous['hash'] if previous else '0' * 64
    created_at = iso()
    event_id = str(uuid.uuid4())
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    digest = hashlib.sha256((prev_hash + event + created_at + encoded).encode('utf-8')).hexdigest()
    db.execute('INSERT INTO audit_events(id,event,transaction_id,payload,created_at,previous_hash,hash) VALUES(?,?,?,?,?,?,?)',
               (event_id, event, transaction_id, encoded, created_at, prev_hash, digest))
    return {'id': event_id, 'type': event, 'transaction_id': transaction_id,
            'payload': payload, 'created_at': created_at, 'hash': digest}


def broadcast(event: dict) -> None:
    dead = []
    with LOCK:
        for subscriber in tuple(SUBSCRIBERS):
            try:
                subscriber.put_nowait(event)
            except Full:
                dead.append(subscriber)
        for subscriber in dead:
            SUBSCRIBERS.discard(subscriber)


def publish_state_event(event_type: str, payload: dict) -> dict:
    with LOCK, connect() as db:
        ev = audit(db, event_type, payload, payload.get('transaction_id'))
    broadcast(ev)
    return ev


def get_state() -> dict:
    with LOCK, connect() as db:
        users = [user_json(row) for row in db.execute('SELECT * FROM users ORDER BY CASE role WHEN \'sender\' THEN 0 WHEN \'scammer\' THEN 1 ELSE 2 END, id')]
        txs = [transaction_json(row) for row in db.execute('SELECT * FROM transactions ORDER BY created_at DESC LIMIT 500')]
        escrows = [transaction_json(row) for row in db.execute("SELECT * FROM transactions WHERE status IN ('ESCROW','MANUAL_REVIEW') ORDER BY created_at")]
        released = db.execute("SELECT COALESCE(SUM(amount_paise),0) FROM transactions WHERE status='RELEASED'").fetchone()[0]
        refunded = db.execute("SELECT COALESCE(SUM(amount_paise),0) FROM transactions WHERE status='REFUNDED'").fetchone()[0]
        approved = db.execute("SELECT COALESCE(SUM(amount_paise),0) FROM transactions WHERE status='APPROVED'").fetchone()[0]
        score_history = [dict(row) for row in db.execute('SELECT id,receiver_id,previous_score,new_score,changed_at,changed_by,decision FROM score_history ORDER BY changed_at DESC LIMIT 100')]
        events = [dict(row) for row in db.execute('SELECT id,event AS type,transaction_id,payload,created_at,previous_hash,hash FROM audit_events ORDER BY sequence DESC LIMIT 100')]
        total_count = db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
        count_by_status = {row['status']: row['count'] for row in db.execute('SELECT status,COUNT(*) AS count FROM transactions GROUP BY status')}
        return {
            'users': users, 'transactions': txs,
            'escrow': money(sum(tx['amount_paise'] for tx in escrows)),
            'escrows': escrows,
            'overview': {
                'registered_users': len(users), 'total_transactions': total_count,
                'status_counts': count_by_status,
                'locked_amount': money(sum(tx['amount_paise'] for tx in escrows)),
                'released_amount': money(released), 'refunded_amount': money(refunded),
                'approved_amount': money(approved),
            },
            'score_history': score_history,
            'events': [{**row, 'payload': json.loads(row['payload'])} for row in events],
            'escrow_timeout_seconds': ESCROW_TIMEOUT_SECONDS,
            'blockchain': {
                'configured': chain_enabled(),
                'connected': None,
                'mode': 'hardhat-local' if chain_enabled() else 'not_configured',
                'note': 'Chain status is confirmed when a contract operation succeeds.' if chain_enabled() else 'Deploy the local escrow contract to enable on-chain escrow.',
            },
        }


def make_admin_token() -> str:
    expires = str(int(time.time()) + ADMIN_SESSION_SECONDS)
    nonce = secrets.token_urlsafe(12)
    body = f'admin:{expires}:{nonce}'
    sig = hmac.new(ADMIN_TOKEN_SECRET, body.encode(), hashlib.sha256).hexdigest()
    return body + ':' + sig


def valid_admin_token(token: str) -> bool:
    try:
        role, expires, nonce, signature = token.split(':', 3)
        body = f'{role}:{expires}:{nonce}'
        expected = hmac.new(ADMIN_TOKEN_SECRET, body.encode(), hashlib.sha256).hexdigest()
        return role == 'admin' and int(expires) >= int(time.time()) and hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def settle_escrow(db: sqlite3.Connection, tx: sqlite3.Row, new_score: int) -> tuple[str, str] | None:
    """Settle one open hold once, based on the newly authenticated score."""
    if tx['status'] not in ('ESCROW', 'MANUAL_REVIEW'):
        return None
    if new_score < 50:
        status, reason, event = 'RELEASED', 'Receiver score fell below 50%; escrow released to receiver.', 'ESCROW_RELEASED'
        db.execute('UPDATE users SET balance_paise=balance_paise+? WHERE id=?', (tx['amount_paise'], tx['receiver_id']))
    elif new_score > 80:
        status, reason, event = 'REFUNDED', 'Receiver score rose above 80%; escrow refunded to sender.', 'ESCROW_REFUNDED'
        db.execute('UPDATE users SET balance_paise=balance_paise+? WHERE id=?', (tx['amount_paise'], tx['sender_id']))
    else:
        return None
    db.execute('UPDATE transactions SET status=?,reason=?,updated_at=?,expires_at=NULL WHERE id=? AND status IN (\'ESCROW\',\'MANUAL_REVIEW\')',
               (status, reason, iso(), tx['id']))
    audit_event = audit(db, event, {'transaction_id': tx['id'], 'score': new_score, 'amount': money(tx['amount_paise'])}, tx['id'])
    return status, audit_event


def timeout_worker() -> None:
    while True:
        time.sleep(1)
        emitted = []
        now = utcnow()
        with LOCK, connect() as db:
            expired = list(db.execute("SELECT * FROM transactions WHERE status='ESCROW' AND expires_at IS NOT NULL AND expires_at<=?", (iso(now),)))
            for tx in expired:
                chain_receipt = None
                if chain_enabled() and tx['blockchain_tx_hash']:
                    try:
                        chain_receipt = call_chain('expire', {'transaction_id': tx['id']})
                    except RuntimeError:
                        # Leave the backend hold open and retry while chain is unavailable.
                        continue
                    if chain_receipt.get('txHash'):
                        db.execute('UPDATE transactions SET blockchain_tx_hash=? WHERE id=?', (chain_receipt['txHash'], tx['id']))
                        emitted.append(audit(db, 'SMART_CONTRACT_EVENT_RECEIVED', {
                            'transaction_id': tx['id'], 'transaction_hash': chain_receipt['txHash'],
                            'events': chain_receipt['events'],
                        }, tx['id']))
                db.execute("UPDATE transactions SET status='MANUAL_REVIEW',reason=?,updated_at=? WHERE id=? AND status='ESCROW'",
                           ('Escrow timed out. Funds remain locked for authenticated admin review.', iso(now), tx['id']))
                emitted.append(audit(db, 'ESCROW_MANUAL_REVIEW', {
                    'transaction_id': tx['id'], 'policy': 'retain_locked_until_admin_review',
                    'amount': money(tx['amount_paise']), 'blockchain_tx_hash': chain_receipt.get('txHash') if chain_receipt else tx['blockchain_tx_hash'],
                }, tx['id']))
        for event in emitted:
            broadcast(event)


class Handler(BaseHTTPRequestHandler):
    server_version = 'ShieldPayDemo/2.0'
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def handle(self):
        # Browsers and curl close long-lived SSE sockets during normal reloads.
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass

    def send_json(self, status: int, obj: dict) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Idempotency-Key')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 16_384:
                raise ValueError('Request body is too large.')
            value = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(value, dict):
                raise ValueError('JSON body must be an object.')
            return value
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Invalid JSON request body.') from exc

    def require_admin(self) -> bool:
        header = self.headers.get('Authorization', '')
        token = header.removeprefix('Bearer ').strip() if header.startswith('Bearer ') else ''
        if valid_admin_token(token):
            return True
        self.send_json(401, {'detail': 'Admin login required.'})
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Idempotency-Key')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Max-Age', '600')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/dashboard.js':
            if not DASHBOARD_SCRIPT.exists():
                return self.send_json(404, {'detail': 'Dashboard script has not been built yet.'})
            content = DASHBOARD_SCRIPT.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path in ('/', '/dashboard', '/dashboard/'):
            if not DASHBOARD_FILE.exists():
                return self.send_json(404, {'detail': 'Dashboard has not been built yet.'})
            content = DASHBOARD_FILE.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == '/health':
            chain = {'configured': chain_enabled(), 'connected': False, 'network': None, 'contract_address': None}
            if chain['configured']:
                try:
                    info = call_chain('inspect', {}, timeout=4)
                    chain.update({'connected': bool(info.get('connected')), 'network': info.get('network'), 'contract_address': info.get('address')})
                except RuntimeError:
                    pass
            return self.send_json(200, {'ok': True, 'simulation_only': True, 'database': str(DATABASE),
                'realtime': 'server-sent-events', 'blockchain': chain})
        if parsed.path == '/api/state':
            return self.send_json(200, get_state())
        if parsed.path == '/api/users':
            return self.send_json(200, {'users': get_state()['users']})
        if parsed.path == '/api/events':
            with LOCK, connect() as db:
                rows = list(db.execute('SELECT id,event AS type,transaction_id,payload,created_at,previous_hash,hash FROM audit_events ORDER BY sequence DESC LIMIT 200'))
            return self.send_json(200, {'events': [{**dict(row), 'payload': json.loads(row['payload'])} for row in rows]})
        if parsed.path == '/api/stream':
            return self.stream_events()
        if parsed.path.startswith('/api/transactions/'):
            txid = parsed.path.rsplit('/', 1)[-1]
            with LOCK, connect() as db:
                row = db.execute('SELECT * FROM transactions WHERE id=?', (txid,)).fetchone()
            if not row:
                return self.send_json(404, {'detail': 'Transaction not found.'})
            return self.send_json(200, {'transaction': transaction_json(row)})
        return self.send_json(404, {'detail': 'Not found.'})

    def stream_events(self):
        q: Queue = Queue(maxsize=100)
        with LOCK:
            SUBSCRIBERS.add(q)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try:
            self.wfile.write(b': ShieldPay event stream connected\n\n')
            self.wfile.flush()
            self.connection.settimeout(20)
            while True:
                try:
                    event = q.get(timeout=15)
                    message = f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                except Empty:
                    message = ': keepalive\n\n'
                self.wfile.write(message.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            with LOCK:
                SUBSCRIBERS.discard(q)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            data = self.body()
        except ValueError as exc:
            return self.send_json(400, {'detail': str(exc)})

        if parsed.path == '/api/admin/login':
            password = str(data.get('password', ''))
            if not hmac.compare_digest(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
                return self.send_json(401, {'detail': 'Invalid admin credentials.'})
            token = make_admin_token()
            ev = publish_state_event('ADMIN_SESSION_STARTED', {'actor': 'admin'})
            return self.send_json(200, {'token': token, 'expires_in': ADMIN_SESSION_SECONDS, 'event': ev})

        if parsed.path == '/api/payments':
            try:
                amount_paise = amount_to_paise(data.get('amount'))
            except ValueError as exc:
                return self.send_json(400, {'detail': str(exc)})
            sender_id, receiver_id = str(data.get('sender_id', '')), str(data.get('receiver_id', ''))
            key = self.headers.get('Idempotency-Key') or str(data.get('idempotency_key', '')) or None
            result_event = None
            with LOCK, connect() as db:
                sender = db.execute('SELECT * FROM users WHERE id=?', (sender_id,)).fetchone()
                receiver = db.execute('SELECT * FROM users WHERE id=?', (receiver_id,)).fetchone()
                if not sender or sender['role'] != 'sender':
                    return self.send_json(400, {'detail': 'Choose one of the three legitimate sender profiles.'})
                if not receiver or receiver['role'] not in ('business', 'scammer') or sender_id == receiver_id:
                    return self.send_json(400, {'detail': 'Choose the business or suspicious demo receiver.'})
                if sender['balance_paise'] < amount_paise:
                    return self.send_json(400, {'detail': 'Not enough simulated wallet balance.'})
                if key:
                    previous = db.execute('SELECT * FROM transactions WHERE idempotency_key=?', (key,)).fetchone()
                    if previous:
                        return self.send_json(200, {'transaction': transaction_json(previous), 'duplicate': True})
                score = receiver['scam_score']
                now_dt = utcnow()
                txid = str(uuid.uuid4())
                if score < 50:
                    status, reason = 'APPROVED', f'Receiver score {score}% is below 50%; payment approved.'
                elif score <= 80:
                    status, reason = 'ESCROW', f'Receiver score {score}% is in the 50%–80% escrow range.'
                else:
                    status, reason = 'REJECTED', f'Receiver score {score}% is above 80%; payment rejected and sender balance is unchanged.'
                expires_at = iso(now_dt + timedelta(seconds=ESCROW_TIMEOUT_SECONDS)) if status == 'ESCROW' else None
                if status == 'APPROVED':
                    db.execute('UPDATE users SET balance_paise=balance_paise-? WHERE id=?', (amount_paise, sender_id))
                    db.execute('UPDATE users SET balance_paise=balance_paise+? WHERE id=?', (amount_paise, receiver_id))
                elif status == 'ESCROW':
                    db.execute('UPDATE users SET balance_paise=balance_paise-? WHERE id=?', (amount_paise, sender_id))
                db.execute('''INSERT INTO transactions(id,sender_id,receiver_id,amount_paise,score,status,reason,created_at,updated_at,expires_at,scenario,idempotency_key)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                           (txid, sender_id, receiver_id, amount_paise, score, status, reason, iso(now_dt), iso(now_dt), expires_at,
                            str(data.get('scenario', 'receiver-score-demo'))[:80], key))
                chain_receipt = None
                if status == 'ESCROW' and chain_enabled():
                    try:
                        chain_receipt = call_chain('create', {
                            'transaction_id': txid, 'sender_id': sender_id, 'receiver_id': receiver_id,
                            'amount_paise': amount_paise, 'score': score, 'expires_at': expires_at,
                        })
                    except RuntimeError as exc:
                        db.rollback()
                        return self.send_json(503, {'detail': f'Blockchain escrow was not created; payment was not recorded. {exc}'})
                    db.execute('UPDATE transactions SET blockchain_tx_hash=? WHERE id=?', (chain_receipt['txHash'], txid))
                    audit(db, 'SMART_CONTRACT_EVENT_RECEIVED', {
                        'transaction_id': txid, 'transaction_hash': chain_receipt['txHash'], 'events': chain_receipt['events'],
                    }, txid)
                result_event = audit(db, 'PAYMENT_' + status, {'transaction_id': txid, 'sender_id': sender_id,
                    'receiver_id': receiver_id, 'amount': money(amount_paise), 'score': score, 'decision': status,
                    'blockchain_tx_hash': chain_receipt['txHash'] if chain_receipt else None}, txid)
                row = db.execute('SELECT * FROM transactions WHERE id=?', (txid,)).fetchone()
                response = transaction_json(row)
            broadcast(result_event)
            broadcast({'id': str(uuid.uuid4()), 'type': 'STATE_UPDATED', 'transaction_id': response['id'], 'payload': {'reason': 'payment_state'}, 'created_at': iso()})
            return self.send_json(201, {'transaction': response, 'id': response['id'], 'status': response['status'], 'reason': response['reason']})

        if parsed.path == '/api/admin/score':
            if not self.require_admin():
                return
            receiver_id = str(data.get('receiver_id', 'business'))
            try:
                raw_score = data.get('score')
                if isinstance(raw_score, bool) or not str(raw_score).isdecimal():
                    raise ValueError
                score = int(raw_score)
                if not 0 <= score <= 100:
                    raise ValueError
            except (ValueError, TypeError):
                return self.send_json(400, {'detail': 'Score must be a whole number from 0 to 100.'})
            emitted = []
            with LOCK, connect() as db:
                receiver = db.execute('SELECT * FROM users WHERE id=?', (receiver_id,)).fetchone()
                if not receiver or receiver['role'] not in ('business', 'scammer'):
                    return self.send_json(400, {'detail': 'Score can only be set for a receiver profile.'})
                previous = receiver['scam_score']
                if score == previous:
                    return self.send_json(200, {'receiver_id': receiver_id, 'previous_score': previous, 'new_score': score,
                        'changed_at': iso(), 'changed_by': 'admin', 'decision': 'NO_CHANGE', 'settled': []})
                chain_receipt = None
                if chain_enabled():
                    try:
                        chain_receipt = call_chain('score', {'receiver_id': receiver_id, 'score': score})
                    except RuntimeError as exc:
                        db.rollback()
                        return self.send_json(503, {'detail': f'Blockchain score update failed; backend score was not changed. {exc}'})
                    db.execute("UPDATE transactions SET blockchain_tx_hash=? WHERE receiver_id=? AND status IN ('ESCROW','MANUAL_REVIEW') AND blockchain_tx_hash IS NOT NULL",
                               (chain_receipt['txHash'], receiver_id))
                    emitted.append(audit(db, 'SMART_CONTRACT_EVENT_RECEIVED', {
                        'receiver_id': receiver_id, 'transaction_hash': chain_receipt['txHash'], 'events': chain_receipt['events'],
                    }))
                db.execute('UPDATE users SET scam_score=? WHERE id=?', (score, receiver_id))
                changed_at = iso()
                decision = 'APPROVED' if score < 50 else ('ESCROW' if score <= 80 else 'REJECTED')
                db.execute('INSERT INTO score_history VALUES(?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()), receiver_id, previous, score, changed_at, 'admin', decision))
                emitted.append(audit(db, 'SCAM_SCORE_UPDATED', {'receiver_id': receiver_id, 'previous_score': previous,
                    'new_score': score, 'changed_by': 'admin', 'decision': decision}))
                open_rows = list(db.execute("SELECT * FROM transactions WHERE receiver_id=? AND status IN ('ESCROW','MANUAL_REVIEW')", (receiver_id,)))
                settled = []
                for tx in open_rows:
                    resolved = settle_escrow(db, tx, score)
                    if resolved:
                        settled.append({'transaction_id': tx['id'], 'status': resolved[0]})
                        emitted.append(resolved[1])
            for event in emitted:
                broadcast(event)
            broadcast({'id': str(uuid.uuid4()), 'type': 'STATE_UPDATED', 'transaction_id': None,
                        'payload': {'reason': 'scam_score_updated'}, 'created_at': iso()})
            return self.send_json(200, {'receiver_id': receiver_id, 'previous_score': previous, 'new_score': score,
                'changed_at': changed_at, 'changed_by': 'admin', 'decision': decision, 'settled': settled,
                'blockchain_tx_hash': chain_receipt['txHash'] if chain_receipt else None,
                'policy': 'below 50 release; 50 through 80 hold; above 80 refund'})

        if parsed.path.startswith('/api/admin/transactions/') and parsed.path.endswith('/refund'):
            if not self.require_admin():
                return
            txid = parsed.path.split('/')[-2]
            with LOCK, connect() as db:
                tx = db.execute('SELECT * FROM transactions WHERE id=?', (txid,)).fetchone()
                if not tx or tx['status'] != 'MANUAL_REVIEW':
                    return self.send_json(409, {'detail': 'Only a timed-out transaction awaiting manual review can be refunded.'})
                if chain_enabled() and tx['blockchain_tx_hash']:
                    try:
                        chain_receipt = call_chain('refund', {'transaction_id': txid})
                    except RuntimeError as exc:
                        db.rollback()
                        return self.send_json(503, {'detail': f'On-chain timeout refund failed; backend state was not changed. {exc}'})
                    if chain_receipt.get('txHash'):
                        db.execute('UPDATE transactions SET blockchain_tx_hash=? WHERE id=?', (chain_receipt['txHash'], txid))
                        audit(db, 'SMART_CONTRACT_EVENT_RECEIVED', {
                            'transaction_id': txid, 'transaction_hash': chain_receipt['txHash'], 'events': chain_receipt['events'],
                        }, txid)
                db.execute('UPDATE users SET balance_paise=balance_paise+? WHERE id=?', (tx['amount_paise'], tx['sender_id']))
                db.execute("UPDATE transactions SET status='REFUNDED',reason=?,updated_at=?,expires_at=NULL WHERE id=? AND status='MANUAL_REVIEW'",
                           ('Admin completed timeout review and refunded sender.', iso(), txid))
                ev = audit(db, 'ESCROW_TIMEOUT_REFUNDED', {'transaction_id': txid, 'amount': money(tx['amount_paise']), 'changed_by': 'admin'}, txid)
                row = db.execute('SELECT * FROM transactions WHERE id=?', (txid,)).fetchone()
            broadcast(ev)
            broadcast({'id': str(uuid.uuid4()), 'type': 'STATE_UPDATED', 'transaction_id': txid, 'payload': {'reason': 'timeout_refund'}, 'created_at': iso()})
            return self.send_json(200, {'transaction': transaction_json(row)})

        if parsed.path == '/api/admin/reset':
            if not self.require_admin():
                return
            chain_receipt = None
            if chain_enabled():
                try:
                    chain_receipt = call_chain('reset', {})
                except RuntimeError as exc:
                    return self.send_json(503, {'detail': f'Local-chain reset could not safely resolve active holds; backend was not reset. {exc}'})
            with LOCK, connect() as db:
                db.execute('DELETE FROM audit_events')
                db.execute('DELETE FROM score_history')
                db.execute('DELETE FROM transactions')
                db.execute('DELETE FROM reports')
                db.execute('DELETE FROM users')
                db.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?)', SEED_USERS)
                ev = audit(db, 'DEMO_RESET', {'actor': 'admin', 'users': len(SEED_USERS),
                    'chain_reset_tx_hash': chain_receipt['txHash'] if chain_receipt else None,
                    'chain_history_preserved': bool(chain_receipt)})
            broadcast(ev)
            broadcast({'id': str(uuid.uuid4()), 'type': 'STATE_UPDATED', 'payload': {'reason': 'demo_reset'}, 'created_at': iso()})
            return self.send_json(200, {'ok': True, 'message': 'Demo state reset to the five seeded profiles.'})

        if parsed.path == '/api/reports':
            reporter_id = str(data.get('reporter_id', ''))
            receiver_id = str(data.get('receiver_id', ''))
            with LOCK, connect() as db:
                reporter = db.execute('SELECT * FROM users WHERE id=?', (reporter_id,)).fetchone()
                receiver = db.execute('SELECT * FROM users WHERE id=?', (receiver_id,)).fetchone()
                if not reporter or not receiver or reporter_id == receiver_id or receiver['role'] not in ('business', 'scammer'):
                    return self.send_json(400, {'detail': 'Choose a valid reporter and receiver profile.'})
                report_id = str(uuid.uuid4())
                db.execute('INSERT OR IGNORE INTO reports VALUES(?,?,?,?)', (report_id, reporter_id, receiver_id, iso()))
                ev = audit(db, 'DEMO_REPORT_RECORDED', {'reporter_id': reporter_id, 'receiver_id': receiver_id})
            broadcast(ev)
            return self.send_json(200, {'ok': True, 'message': 'Demo report recorded. Scores remain admin-configured.'})

        return self.send_json(404, {'detail': 'Not found.'})


def main() -> None:
    init_database()
    Thread(target=timeout_worker, name='escrow-timeout-worker', daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f'ShieldPay demo backend listening on http://{HOST}:{PORT}; SQLite={DATABASE}; simulated funds only', flush=True)
    print(f'Admin demo password is configured via SHIELDPAY_ADMIN_PASSWORD (default: shieldpay-admin); escrow timeout={ESCROW_TIMEOUT_SECONDS}s', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShieldPay backend stopping.', flush=True)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

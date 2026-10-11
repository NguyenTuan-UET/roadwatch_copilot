"""Local web accounts and revocable sessions. Never imported by perception or decisions."""
import hashlib
import hmac
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from .schemas import Account, Credentials


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthStore:
    def __init__(self, path: Path, session_seconds: int = 43200) -> None:
        self.path, self.session_seconds = Path(path), session_seconds

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as connection, connection:
            self.path.chmod(0o600)
            if connection.execute('PRAGMA user_version').fetchone()[0] not in (0, 1):
                raise ValueError(f'{self.path}: phiên bản database tài khoản chưa được hỗ trợ')
            connection.execute('PRAGMA foreign_keys = ON')
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash BLOB NOT NULL, '
                               'salt BLOB NOT NULL, role TEXT NOT NULL CHECK(role IN (\'driver\', \'engineer\')))')
            connection.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL '
                               'REFERENCES users(username), expires_unix REAL NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, failures INTEGER NOT NULL, '
                               'retry_after_unix REAL NOT NULL)')
            connection.execute('PRAGMA user_version = 1')
            yield connection

    def register(self, username: str, password: str) -> Account:
        Credentials(username=username, password=password)
        salt = secrets.token_bytes(16)
        hashed = _password_hash(password, salt)
        try:
            with self._connect() as connection:
                connection.execute("INSERT INTO users VALUES (?, ?, ?, 'driver')", (username, hashed, salt))
        except sqlite3.IntegrityError as exc:
            raise ValueError('Tên đăng nhập đã được sử dụng') from exc
        return Account(username=username, role='driver')

    def bootstrap_engineer(self, username: str, password: str) -> None:
        Credentials(username=username, password=password)
        with self._connect() as connection:
            if connection.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
                return  # Existing accounts and passwords are never overwritten from environment settings.
            salt = secrets.token_bytes(16)
            connection.execute("INSERT INTO users VALUES (?, ?, ?, 'engineer')", (username, _password_hash(password, salt), salt))

    def authenticate(self, username: str, password: str, now: float | None = None) -> Account | None:
        now = time.time() if now is None else now
        blocked = False
        account = None
        with self._connect() as connection:
            connection.execute('DELETE FROM login_attempts WHERE retry_after_unix <= ?', (now,))
            attempts = connection.execute('SELECT failures FROM login_attempts WHERE username = ?', (username,)).fetchone()
            if attempts and attempts[0] >= 5:
                blocked = True
            else:
                user = connection.execute('SELECT password_hash, salt, role FROM users WHERE username = ?', (username,)).fetchone()
                hashed = _password_hash(password, bytes(user[1]) if user else b'\0' * 16)
                if user and hmac.compare_digest(hashed, bytes(user[0])):
                    connection.execute('DELETE FROM login_attempts WHERE username = ?', (username,))
                    account = Account(username=username, role=user[2])
                else:
                    connection.execute('INSERT INTO login_attempts VALUES (?, 1, ?) ON CONFLICT(username) DO UPDATE '
                                       'SET failures = failures + 1, retry_after_unix = excluded.retry_after_unix', (username, now + 300))
        if blocked:
            raise ValueError('Đăng nhập sai nhiều lần; thử lại sau 5 phút')
        return account

    def create_session(self, account: Account, now: float | None = None) -> str:
        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute('DELETE FROM sessions WHERE expires_unix <= ?', (now,))
            connection.execute('INSERT INTO sessions VALUES (?, ?, ?)', (_token_hash(token), account.username, now + self.session_seconds))
        return token

    def session_user(self, token: str, now: float | None = None) -> Account | None:
        if not token or len(token) > 100:
            return None
        now = time.time() if now is None else now
        with self._connect() as connection:
            user = connection.execute('SELECT users.username, users.role FROM sessions JOIN users USING(username) '
                                      'WHERE token_hash = ? AND expires_unix > ?', (_token_hash(token), now)).fetchone()
        return Account(username=user[0], role=user[1]) if user else None

    def revoke(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute('DELETE FROM sessions WHERE token_hash = ?', (_token_hash(token),))

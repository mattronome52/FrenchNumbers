import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'numbers.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        schema = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema) as f:
            conn.executescript(f.read())


def get_user_by_username(username):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(uid):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
        return dict(row) if row else None


def create_user(username, password_hash):
    with get_db() as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash),
        )


def save_preferences(uid, voice_pref, speed_pref, session_size, exercise_type):
    with get_db() as conn:
        conn.execute(
            '''UPDATE users
               SET voice_pref=?, speed_pref=?, session_size=?, exercise_type=?
               WHERE id=?''',
            (voice_pref, speed_pref, session_size, exercise_type, uid),
        )

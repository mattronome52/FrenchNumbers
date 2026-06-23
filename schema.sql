CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    voice_pref    TEXT    NOT NULL DEFAULT 'female',
    speed_pref    TEXT    NOT NULL DEFAULT 'normal',
    session_size  INTEGER NOT NULL DEFAULT 10,
    exercise_type TEXT    NOT NULL DEFAULT 'all'
);

# French Numbers — CLAUDE.md

## Purpose
A web-based French listening drill for numbers. The app speaks a number, date, or price in French using the browser's Text-to-Speech engine, and the user types what they heard. Designed to build comprehension of spoken French numbers (years, large numbers, euro prices).

## How to run

```bash
# First time only
python populate_db.py

# Every time
env/bin/python app.py
# → http://localhost:5002
```

The virtual environment (`env/`) is already created with Flask and Werkzeug installed.

## File structure

```
FrenchNumbers/
├── app.py            # Flask app — routes, number generation, answer checking
├── database.py       # SQLite helpers (users + preferences)
├── schema.sql        # DB schema (users table)
├── populate_db.py    # Creates numbers.db from schema.sql
├── requirements.txt  # flask, werkzeug
├── numbers.db        # SQLite database (created by populate_db.py)
├── templates/
│   ├── index.html    # Main exercise page
│   ├── login.html
│   └── register.html
└── static/
    ├── style.css     # Amber/dotted-grid palette (matches FrenchPrepositions)
    └── script.js     # Web Speech API, session logic, answer submission
```

## Architecture

**Backend (app.py)**
- Flask with server-side sessions (no database for exercise items — they're generated fresh each session)
- Number generation happens in Python at session start; items are stored in the Flask session as a JSON list
- `/api/session/start` — generates N items of the chosen type, stores in `session['item_queue']`
- `/api/item` — returns `queue[0]` (peek, don't pop)
- `/api/answer` — pops the front of the queue, checks the answer, returns result + session status
- `/api/session/redo` — shuffles `last_item_queue` (a copy saved at session start) into a new queue
- Preferences (voice, speed, session size, exercise type) are saved to SQLite per user

**Frontend (script.js)**
- Web Speech API (`speechSynthesis`) handles all audio — no server-side TTS
- French voice selected by filtering `speechSynthesis.getVoices()` for `lang.startsWith('fr')`, then matching known male/female voice name substrings (Thomas, Amelie, etc.)
- Speed maps: slow → 0.6×, normal → 0.9×, fast → 1.2×
- Audio plays automatically when an item loads (300 ms delay to let voices initialise)
- Answer submitted with Enter key or Submit button

**Exercise types**
| Type | Range | User types |
|---|---|---|
| `years` | 1900–2025 | The 4-digit year |
| `prices` | €1–€999, optionally with cents | e.g. `45.50` or `45,50` |
| `numbers` | 100–99,999,999 (three tiers) | The number, no formatting needed |
| `all` | Random mix of the above | Depends on type |

**Answer checking** is flexible:
- Prices: normalise comma/period, strip `€`, compare as floats (±0.005 tolerance)
- Years/numbers: strip all spaces and punctuation, compare as integers

## Database schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    voice_pref    TEXT    NOT NULL DEFAULT 'female',   -- 'female' | 'male'
    speed_pref    TEXT    NOT NULL DEFAULT 'normal',   -- 'slow' | 'normal' | 'fast'
    session_size  INTEGER NOT NULL DEFAULT 10,
    exercise_type TEXT    NOT NULL DEFAULT 'all'       -- 'all' | 'years' | 'prices' | 'numbers'
);
```

## Port
Runs on **5002** (FrenchPrepositions uses 5001).

## Sibling project
The French Prepositions flashcard app lives at `../FrenchPrepositions/` and runs on port 5001. It uses the same visual design (amber palette, dotted background, Georgia serif font) but is card-based with button answers and a SQLite card database.

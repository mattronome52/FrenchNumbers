import os
import random
import functools
from flask import (Flask, render_template, jsonify, request,
                   session, redirect, url_for, flash)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import database

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'numbers-dev-secret-change-me')


# ── Auth helpers ───────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    uid = session.get('user_id')
    return database.get_user_by_id(uid) if uid else None


# ── Number / date / price generation ──────────────────────────────────────────

def generate_year():
    year = random.randint(1900, 2025)
    return {
        'type':    'year',
        'spoken':  str(year),
        'answer':  str(year),
        'display': str(year),
        'prompt':  'Quelle année avez-vous entendue ?',
        'hint':    'Type the 4-digit year, e.g. 1998',
    }


def generate_price():
    euros = random.randint(1, 999)
    use_cents = random.random() < 0.6
    if use_cents:
        cents = random.choice([5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 99]
                              + [random.randint(1, 99)])
    else:
        cents = 0

    if cents == 0:
        spoken  = f"{euros} euros"
        answer  = str(euros)
        display = f"{euros} €"
        hint    = f'Type the euro amount, e.g. {euros}'
    else:
        spoken  = f"{euros} euros {cents} centimes"
        answer  = f"{euros}.{cents:02d}"
        display = f"{euros},{cents:02d} €"
        hint    = f'Type euros and cents, e.g. {euros}.{cents:02d} or {euros},{cents:02d}'

    return {
        'type':    'price',
        'spoken':  spoken,
        'answer':  answer,
        'display': display,
        'prompt':  'Quel prix avez-vous entendu ?',
        'hint':    hint,
    }


def generate_large_number():
    tier = random.choices(
        ['hundreds', 'thousands', 'millions'],
        weights=[3, 4, 3],
    )[0]
    if tier == 'hundreds':
        n = random.randint(100, 9999)
    elif tier == 'thousands':
        n = random.randint(10_000, 999_999)
    else:
        n = random.randint(1_000_000, 99_999_999)

    # French formatting uses space as thousands separator
    display = f"{n:,}".replace(',', ' ')
    return {
        'type':    'number',
        'spoken':  str(n),
        'answer':  str(n),
        'display': display,
        'prompt':  'Quel nombre avez-vous entendu ?',
        'hint':    'Type the number without spaces or punctuation',
    }


GENERATORS = {
    'years':   generate_year,
    'prices':  generate_price,
    'numbers': generate_large_number,
}


def generate_item(exercise_type):
    if exercise_type == 'all':
        return random.choice(list(GENERATORS.values()))()
    return GENERATORS.get(exercise_type, generate_year)()


def build_session_items(size, exercise_type):
    return [generate_item(exercise_type) for _ in range(size)]


# ── Answer checking ────────────────────────────────────────────────────────────

def check_answer(user_answer, item):
    user = user_answer.strip()
    if item['type'] == 'price':
        # Accept comma or period as decimal separator; ignore € and whitespace
        user = (user.replace(',', '.').replace(' ', '')
                    .replace('€', '').replace('euros', '').strip())
        correct = item['answer'].replace(',', '.')
        try:
            return abs(float(user) - float(correct)) < 0.005
        except ValueError:
            return False
    else:
        # Year or large number: strip all formatting, compare as integers
        user    = user.replace(' ', '').replace(',', '').replace('.', '').replace(' ', '')
        correct = item['answer'].replace(' ', '').replace(' ', '')
        try:
            return int(user) == int(correct)
        except ValueError:
            return False


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = database.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')
        if not username:
            flash('Username is required.')
        elif len(password) < 4:
            flash('Password must be at least 4 characters.')
        elif password != confirm:
            flash('Passwords do not match.')
        else:
            try:
                database.create_user(username, generate_password_hash(password))
                flash('Account created — please log in.')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('That username is already taken.')
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Main page ──────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    user = current_user()
    return render_template('index.html', username=user['username'])


# ── Item API ───────────────────────────────────────────────────────────────────

@app.route('/api/item')
@login_required
def get_item():
    queue = session.get('item_queue')
    if not queue:
        return jsonify({'error': 'No active session'}), 404
    return jsonify(queue[0])


@app.route('/api/answer', methods=['POST'])
@login_required
def submit_answer():
    data = request.get_json()
    if not data or 'answer' not in data:
        return jsonify({'error': 'Missing answer'}), 400

    queue = session.get('item_queue')
    if not queue:
        return jsonify({'error': 'No active session'}), 404

    item    = queue[0]
    correct = check_answer(data['answer'], item)

    # Always advance — no retry loop
    session['item_queue']       = queue[1:]
    session['session_answered'] = session.get('session_answered', 0) + 1
    if correct:
        session['session_correct'] = session.get('session_correct', 0) + 1
    session.modified = True

    total     = session.get('session_total', 0)
    answered  = session.get('session_answered', 0)
    remaining = len(session['item_queue'])

    return jsonify({
        'correct':        correct,
        'correct_answer': item['answer'],
        'display':        item['display'],
        'session_status': {
            'total':     total,
            'answered':  answered,
            'correct':   session.get('session_correct', 0),
            'remaining': remaining,
            'complete':  remaining == 0,
        },
    })


# ── Session management ─────────────────────────────────────────────────────────

@app.route('/api/session/start', methods=['POST'])
@login_required
def session_start():
    data = request.get_json() or {}
    user = current_user()

    size          = int(data.get('session_size')  or user.get('session_size')  or 10)
    exercise_type = data.get('exercise_type')      or user.get('exercise_type') or 'all'

    size  = max(1, min(50, size))
    items = build_session_items(size, exercise_type)

    session['item_queue']        = items
    session['last_item_queue']   = list(items)
    session['session_total']     = size
    session['session_answered']  = 0
    session['session_correct']   = 0
    session.modified = True

    return jsonify({'total': size, 'answered': 0, 'correct': 0,
                    'remaining': size, 'complete': False})


@app.route('/api/session/redo', methods=['POST'])
@login_required
def session_redo():
    last = session.get('last_item_queue')
    if not last:
        return jsonify({'error': 'No previous session'}), 404

    shuffled = list(last)
    random.shuffle(shuffled)

    session['item_queue']       = shuffled
    session['session_total']    = len(shuffled)
    session['session_answered'] = 0
    session['session_correct']  = 0
    session.modified = True

    return jsonify({'total': len(shuffled), 'answered': 0, 'correct': 0,
                    'remaining': len(shuffled), 'complete': False})


@app.route('/api/session/status')
@login_required
def session_status():
    queue = session.get('item_queue')
    if queue is None:
        return jsonify({'active': False})
    total     = session.get('session_total', 0)
    answered  = session.get('session_answered', 0)
    correct   = session.get('session_correct', 0)
    return jsonify({
        'active':    True,
        'total':     total,
        'answered':  answered,
        'correct':   correct,
        'remaining': len(queue),
        'complete':  len(queue) == 0,
    })


@app.route('/api/session/end', methods=['POST'])
@login_required
def session_end():
    for key in ('item_queue', 'session_total', 'session_answered', 'session_correct'):
        session.pop(key, None)
    session.modified = True
    return jsonify({'ok': True})


# ── Preferences API ────────────────────────────────────────────────────────────

@app.route('/api/preferences', methods=['GET'])
@login_required
def get_preferences():
    user = current_user()
    return jsonify({
        'voice_pref':    user['voice_pref'],
        'speed_pref':    user['speed_pref'],
        'session_size':  user['session_size'],
        'exercise_type': user['exercise_type'],
    })


@app.route('/api/preferences', methods=['POST'])
@login_required
def save_user_preferences():
    data          = request.get_json() or {}
    voice_pref    = data.get('voice_pref', 'female')
    speed_pref    = data.get('speed_pref', 'normal')
    session_size  = max(1, min(50, int(data.get('session_size', 10))))
    exercise_type = data.get('exercise_type', 'all')
    database.save_preferences(
        session['user_id'], voice_pref, speed_pref, session_size, exercise_type
    )
    return jsonify({'ok': True})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)

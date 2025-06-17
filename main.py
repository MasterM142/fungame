from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

# Database setup
def init_db():
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    
    # Users table with admin flag
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  balance REAL DEFAULT 1000.0,
                  total_won REAL DEFAULT 0.0,
                  total_wagered REAL DEFAULT 0.0,
                  games_played INTEGER DEFAULT 0,
                  is_admin INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Games table
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  game_type TEXT NOT NULL,
                  bet_amount REAL NOT NULL,
                  win_amount REAL DEFAULT 0.0,
                  multiplier REAL DEFAULT 0.0,
                  mines_count INTEGER,
                  gems_found INTEGER,
                  dice_number INTEGER,
                  dice_prediction TEXT,
                  dice_target INTEGER,
                  blackjack_player_hand TEXT,
                  blackjack_dealer_hand TEXT,
                  blackjack_result TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

def get_user():
    if 'user_id' in session:
        conn = sqlite3.connect('fungames.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            return {
                'id': user_data[0],
                'username': user_data[1],
                'email': user_data[2],
                'balance': user_data[4],
                'total_won': user_data[5],
                'total_wagered': user_data[6],
                'games_played': user_data[7],
                'is_admin': user_data[8]  # Added admin flag
            }
    return None

def get_recent_games(user_id, limit=10):
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('''SELECT game_type, bet_amount, win_amount, multiplier, mines_count, 
                        created_at FROM games 
                 WHERE user_id = ? 
                 ORDER BY created_at DESC 
                 LIMIT ?''', (user_id, limit))
    games = c.fetchall()
    conn.close()
    
    recent_games = []
    for game in games:
        recent_games.append({
            'game_type': game[0],
            'bet_amount': game[1],
            'win_amount': game[2],
            'multiplier': game[3],
            'mines_count': game[4],
            'created_at': datetime.fromisoformat(game[5])
        })
    
    return recent_games

def calculate_mines_multiplier(gems_found, mines_count):
    if gems_found == 0:
        return 1.0
    
    total_cells = 25
    safe_cells = total_cells - mines_count
    
    multiplier = 1.0
    for i in range(gems_found):
        remaining_safe = safe_cells - i
        remaining_total = total_cells - i
        multiplier *= remaining_total / remaining_safe
    
    return multiplier * 0.97

@app.route('/')
def index():
    user = get_user()
    recent_games = []
    if user:
        recent_games = get_recent_games(user['id'])
    return render_template('index.html', user=user, recent_games=recent_games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if len(username) < 3:
            flash('Benutzername muss mindestens 3 Zeichen lang sein')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Passwort muss mindestens 6 Zeichen lang sein')
            return render_template('register.html')
        
        conn = sqlite3.connect('fungames.db')
        c = conn.cursor()
        
        # Check if username or email already exists
        c.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if c.fetchone():
            flash('Benutzername oder E-Mail bereits vergeben')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                  (username, email, password_hash))
        conn.commit()
        conn.close()
        
        flash('Registrierung erfolgreich! Du kannst dich jetzt anmelden.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('fungames.db')
        c = conn.cursor()
        c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        else:
            flash('Ungültige Anmeldedaten')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/mines')
def mines():
    user = get_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('mines.html', user=user)

@app.route('/dice')
def dice():
    user = get_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('dice.html', user=user)

@app.route('/blackjack')
def blackjack():
    user = get_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('blackjack.html', user=user)

# Admin routes
@app.route('/admin')
def admin_panel():
    user = get_user()
    if not user or not user.get('is_admin', 0):
        flash('Zugriff verweigert!')
        return redirect(url_for('index'))
    
    # Get all users for admin to manage
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('SELECT id, username, email, balance, total_won, total_wagered, games_played, is_admin FROM users')
    users = c.fetchall()
    conn.close()
    
    users_list = []
    for u in users:
        users_list.append({
            'id': u[0],
            'username': u[1],
            'email': u[2],
            'balance': u[3],
            'total_won': u[4],
            'total_wagered': u[5],
            'games_played': u[6],
            'is_admin': u[7]
        })
    
    return render_template('admin.html', user=user, users=users_list)

@app.route('/admin/update_balance', methods=['POST'])
def update_balance():
    user = get_user()
    if not user or not user.get('is_admin', 0):
        return jsonify({'error': 'Zugriff verweigert'}), 403
    
    data = request.json
    user_id = data.get('user_id')
    new_balance = float(data.get('balance', 0))
    
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/toggle_admin', methods=['POST'])
def toggle_admin():
    user = get_user()
    if not user or not user.get('is_admin', 0):
        return jsonify({'error': 'Zugriff verweigert'}), 403
    
    data = request.json
    user_id = data.get('user_id')
    is_admin = int(data.get('is_admin', 0))
    
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API-Endpunkt für Benutzerstatistiken
@app.route('/api/user/stats', methods=['GET'])
def get_user_stats():
    user = get_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    return jsonify({
        'balance': user['balance'],
        'games_played': user['games_played'],
        'total_won': user['total_won'],
        'total_wagered': user['total_wagered']
    })

@app.route('/mines/start', methods=['POST'])
def mines_start():
    user = get_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    bet_amount = float(data.get('bet_amount', 0))
    mines_count = int(data.get('mines_count', 3))
    
    if bet_amount <= 0 or bet_amount > user['balance']:
        return jsonify({'success': False, 'error': 'Invalid bet amount'}), 400
    
    if mines_count not in [3, 5, 7]:
        return jsonify({'success': False, 'error': 'Invalid mines count'}), 400
    
    # Generate mine positions
    mine_positions = random.sample(range(25), mines_count)
    
    # Store game state in session - vollständig zurücksetzen
    session['mines_game'] = {
        'bet_amount': bet_amount,
        'mines_count': mines_count,
        'mine_positions': mine_positions,
        'revealed_positions': [],
        'gems_found': 0,
        'active': True,
        'game_over': False  # Explizit auf false setzen
    }
    
    # Update user balance
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (bet_amount, user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'mines_count': mines_count,
        'reset': True  # Signal ans Frontend, dass ein neues Spiel gestartet wurde
    })

@app.route('/mines/reveal', methods=['POST'])
def mines_reveal():
    user = get_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    if 'mines_game' not in session or not session['mines_game']['active']:
        return jsonify({'success': False, 'error': 'No active game'}), 400
    
    data = request.json
    position = int(data.get('position', -1))
    
    if position < 0 or position >= 25:
        return jsonify({'error': 'Invalid position'}), 400
    
    game = session['mines_game']
    
    if position in game['revealed_positions']:
        return jsonify({'error': 'Position already revealed'}), 400
    
    game['revealed_positions'].append(position)
    
    # Check if it's a mine
    if position in game['mine_positions']:
        # Game over - hit a mine
        game['active'] = False
        session['mines_game'] = game  # Speichere aktualisiertes Spiel in der Session
        
        # Save game to database
        conn = sqlite3.connect('fungames.db')
        c = conn.cursor()
        c.execute('''INSERT INTO games (user_id, game_type, bet_amount, win_amount, multiplier, 
                                       mines_count, gems_found) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user['id'], 'mines', game['bet_amount'], 0, 0, 
                   game['mines_count'], game['gems_found']))
        
        # Update user stats
        c.execute('UPDATE users SET games_played = games_played + 1, total_wagered = total_wagered + ? WHERE id = ?',
                  (game['bet_amount'], user['id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': False,
            'mine': True,
            'mine_positions': game['mine_positions'],
            'game_over': True
        })
    else:
        # Found a gem
        game['gems_found'] += 1
        session['mines_game'] = game  # Speichere aktualisiertes Spiel in der Session
        
        # Calculate multiplier
        multiplier = calculate_mines_multiplier(game['gems_found'], game['mines_count'])
        
        return jsonify({
            'success': True,
            'mine': False,
            'gems_found': game['gems_found'],
            'multiplier': multiplier
        })

@app.route('/mines/cashout', methods=['POST'])
def mines_cashout():
    user = get_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Debug-Ausgabe
    print("Session:", session)
    
    if 'mines_game' not in session:
        return jsonify({'success': False, 'error': 'No game in session'}), 400
    
    game = session['mines_game']
    
    # Debug-Ausgabe
    print("Game state:", game)
    print("Gems found:", game.get('gems_found', 0))
    print("Active:", game.get('active', False))
    
    if not game.get('active', False):
        return jsonify({'success': False, 'error': 'Game not active'}), 400
    
    if game.get('gems_found', 0) == 0:
        return jsonify({'success': False, 'error': 'No gems found'}), 400
    
    # Calculate winnings
    multiplier = calculate_mines_multiplier(game['gems_found'], game['mines_count'])
    win_amount = game['bet_amount'] * multiplier
    
    # Update user balance
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ?, total_won = total_won + ?, games_played = games_played + 1, total_wagered = total_wagered + ? WHERE id = ?',
              (win_amount, win_amount, game['bet_amount'], user['id']))
    
    # Save game to database
    c.execute('''INSERT INTO games (user_id, game_type, bet_amount, win_amount, multiplier, 
                                   mines_count, gems_found) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user['id'], 'mines', game['bet_amount'], win_amount, multiplier, 
               game['mines_count'], game['gems_found']))
    
    conn.commit()
    conn.close()
    
    # End game
    game['active'] = False
    session['mines_game'] = game
    
    return jsonify({
        'success': True,
        'win_amount': win_amount,
        'multiplier': multiplier,
        'new_balance': user['balance'] + win_amount
    })

@app.route('/api/dice/roll', methods=['POST'])
def roll_dice():
    user = get_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    bet_amount = float(data.get('bet_amount', 0))
    prediction = data.get('prediction', 'over')  # 'over' or 'under'
    target_number = int(data.get('target_number', 50))
    
    if bet_amount <= 0 or bet_amount > user['balance']:
        return jsonify({'error': 'Invalid bet amount'}), 400
    
    if target_number < 1 or target_number > 99:
        return jsonify({'error': 'Invalid target number'}), 400
    
    if prediction not in ['over', 'under']:
        return jsonify({'error': 'Invalid prediction'}), 400
    
    # Roll the dice (1-100)
    dice_result = random.randint(1, 100)
    
    # Calculate if win
    won = False
    if prediction == 'over' and dice_result > target_number:
        won = True
    elif prediction == 'under' and dice_result < target_number:
        won = True
    
    # Calculate multiplier and winnings
    if prediction == 'over':
        win_chance = (99 - target_number) / 100
    else:
        win_chance = target_number / 100
    
    multiplier = 0.99 / win_chance if win_chance > 0 else 0
    win_amount = bet_amount * multiplier if won else 0
    
    # Update database
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    
    if won:
        new_balance = user['balance'] + win_amount - bet_amount
        c.execute('UPDATE users SET balance = ?, total_won = total_won + ?, games_played = games_played + 1, total_wagered = total_wagered + ? WHERE id = ?',
                  (new_balance, win_amount, bet_amount, user['id']))
    else:
        new_balance = user['balance'] - bet_amount
        c.execute('UPDATE users SET balance = ?, games_played = games_played + 1, total_wagered = total_wagered + ? WHERE id = ?',
                  (new_balance, bet_amount, user['id']))
    
    # Save game to database
    c.execute('''INSERT INTO games (user_id, game_type, bet_amount, win_amount, multiplier, 
                                   dice_number, dice_prediction, dice_target) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user['id'], 'dice', bet_amount, win_amount, multiplier if won else 0, 
               dice_result, prediction, target_number))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'dice_result': dice_result,
        'won': won,
        'win_amount': win_amount,
        'new_balance': new_balance
    })

# Erstelle einen Admin-Benutzer
def create_admin():
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    
    # Prüfe, ob der Admin-Benutzer bereits existiert
    c.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    if c.fetchone():
        print("Admin-Benutzer existiert bereits")
    else:
        # Erstelle Admin-Benutzer
        password_hash = generate_password_hash('admin123')  # Sicheres Passwort verwenden!
        c.execute('INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
                  ('admin', 'admin@example.com', password_hash, 1))
        conn.commit()
        print("Admin-Benutzer erstellt")
    
    conn.close()

def update_db_schema():
    conn = sqlite3.connect('fungames.db')
    c = conn.cursor()
    
    # Prüfe, ob die is_admin-Spalte bereits existiert
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'is_admin' not in columns:
        print("Füge is_admin-Spalte zur users-Tabelle hinzu...")
        try:
            c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            conn.commit()
            print("Datenbank-Schema erfolgreich aktualisiert!")
        except sqlite3.Error as e:
            print(f"Fehler beim Aktualisieren des Schemas: {e}")
    else:
        print("is_admin-Spalte existiert bereits.")
    
    conn.close()

# Ändere die main-Funktion
if __name__ == '__main__':
    init_db()
    update_db_schema()  # Schema aktualisieren
    create_admin()  # Admin-Benutzer erstellen
    app.run(debug=True)

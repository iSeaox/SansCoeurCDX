import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import click

def compute_score(hands_data):
	taker = hands_data["taker_team"]
	defender = "B" if taker == "A" else "A"
	final_score = {}

	if hands_data["contract"] == "Capot":
		if hands_data[taker]["pre_score"] == 162:
			final_score = {taker: 500, defender: 0}
		else:
			final_score = {taker: 0, defender: 160}
	elif hands_data["contract"] == "Générale":
		if hands_data["general"] and hands_data[taker]["pre_score"] == 162 and hands_data["general"]:
			final_score = {taker: 750, defender: 0}
		else:
			final_score = {taker: 0, defender: 160}
	else:
		if hands_data[taker]["pre_score"] < 81:
			final_score = {taker: 0, defender: 160}
		else:
			belote_pts = 10 if hands_data["trump"] == "Tout atout" else 20
			temp_score = {"A": hands_data["A"]["pre_score"] + belote_pts * hands_data["A"]["belote"],
					"B": hands_data["B"]["pre_score"] + belote_pts * hands_data["B"]["belote"]}
			print(temp_score, hands_data)
			if temp_score[taker] >= int(hands_data["contract"]):
				final_score = {
					taker: int(hands_data["contract"]) + hands_data[taker]["pre_score"],
					defender: hands_data[defender]["pre_score"]
				}
			else:
				final_score = {
					taker: 0,
					defender: 160 + temp_score[defender]
				}

		if hands_data[defender]["pre_score"] == 162:
			final_score[defender] += 90
		elif hands_data[taker]["pre_score"] == 162:
			final_score[taker] += 90
				
	mul = 2 if hands_data["coinche"] else (4 if hands_data["surcoinche"] else 1)
	if final_score[taker] == 0:
		final_score[defender] *= mul
	else:
		final_score[taker] *= mul

	belote_pts = 10 if hands_data["trump"] == "Tout atout" else 20
	final_score["A"] += belote_pts * hands_data["A"]["belote"]
	final_score["B"] += belote_pts * hands_data["B"]["belote"]

	return final_score

def create_app():
	# Load environment variables from .env if present
	load_dotenv()

	app = Flask(__name__)
	# In production, use a strong random secret and store securely
	app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
	# Allow overriding DB path via env; fallback to app.root_path/coinche.db
	app.config['DATABASE'] = os.environ.get('DATABASE', os.path.join(app.root_path, 'data/coinche.db'))
	# If env provided a relative path, resolve it under app.root_path
	if not os.path.isabs(app.config['DATABASE']):
		app.config['DATABASE'] = os.path.join(app.root_path, app.config['DATABASE'])
	# Server runtime config
	app.config['HOST'] = os.environ.get('HOST', '0.0.0.0')
	app.config['PORT'] = int(os.environ.get('PORT', 5000))
	app.config['DEBUG'] = os.environ.get('DEBUG', 'true').strip().lower() in ('1', 'true', 'yes', 'on')

	# Harden session cookies
	app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
	app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
	app.config.setdefault('SESSION_COOKIE_SECURE', not app.config['DEBUG'])
	app.config.setdefault('PERMANENT_SESSION_LIFETIME', timedelta(hours=8))

	@app.before_request
	def before_request():
		g.db = get_db(app)

	@app.teardown_request
	def teardown_request(exception):
		db = getattr(g, 'db', None)
		if db is not None:
			db.close()

	# ----- Routes -----
	@app.route('/')
	def index():
		return render_template('index.html')

	@app.route('/login', methods=['GET', 'POST'])
	def login():
		if request.method == 'POST':
			username = request.form.get('username', '').strip()
			password = request.form.get('password', '').strip()
			if not username or not password:
				flash('Identifiants invalides.', 'danger')
				return render_template('login.html')
			# Fetch user by username (case-insensitive)
			with closing(g.db.cursor()) as cur:
				cur.execute(
					"SELECT id, username, password_hash, is_active FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
					(username,),
				)
				row = cur.fetchone()
			if row and row[3] and check_password_hash(row[2], password):
				session.clear()
				session['user_id'] = row[0]
				session['user'] = row[1]
				flash('Connexion réussie.', 'success')
				return redirect(url_for('index'))
			flash('Identifiants invalides.', 'danger')
		return render_template('login.html')

	@app.route('/logout')
	def logout():
		session.clear()
		flash('Déconnecté.', 'info')
		return redirect(url_for('index'))

	def login_required():
		if not session.get('user'):
			flash('Veuillez vous connecter pour continuer.', 'warning')
			return False
		return True

	@app.route('/games')
	def games_list():
		with closing(g.db.cursor()) as cur:
			cur.execute(
				"""
				SELECT g.id,
				       g.created_at,
				       g.updated_at,
				       g.state,
				       g.points_team_a,
				       g.points_team_b,
				       g.target_points,
				       (SELECT group_concat(u.username, ', ')
				        FROM game_players gp JOIN users u ON u.id = gp.user_id
				        WHERE gp.game_id = g.id AND gp.team = 'A') AS team_a,
				       (SELECT group_concat(u.username, ', ')
				        FROM game_players gp JOIN users u ON u.id = gp.user_id
				        WHERE gp.game_id = g.id AND gp.team = 'B') AS team_b
				FROM games g
				ORDER BY g.created_at DESC
				"""
			)
			games = [
				{
					'id': r[0],
					'created_at': r[1],
					'updated_at': r[2],
					'state': r[3],
					'score_a': r[4],
					'score_b': r[5],
					'target_points': r[6],
					'team_a': r[7] or '-',
					'team_b': r[8] or '-',
				}
				for r in cur.fetchall()
			]
		return render_template('games.html', games=games)

	@app.route('/games/<int:game_id>', methods=['GET', 'POST'])
	def game_detail(game_id: int):
		# Load game, players, hands
		with closing(g.db.cursor()) as cur:
			cur.execute(
				"SELECT id, created_at, updated_at, created_by, state, points_team_a, points_team_b, target_points FROM games WHERE id = ?",
				(game_id,),
			)
			game_row = cur.fetchone()
			if not game_row:
				flash("Partie introuvable.", 'warning')
				return redirect(url_for('games_list'))
			game = {
				'id': game_row[0],
				'created_at': game_row[1],
				'updated_at': game_row[2],
				'created_by': game_row[3],
				'state': game_row[4],
				'score_a': game_row[5],
				'score_b': game_row[6],
				'target_points': game_row[7],
			}
			# Players
			cur.execute(
				"SELECT gp.user_id, u.username, gp.team, gp.position FROM game_players gp JOIN users u ON u.id = gp.user_id WHERE gp.game_id = ? ORDER BY gp.team, gp.position",
				(game_id,),
			)
			players = cur.fetchall()
			team_a = [p for p in players if p[2] == 'A']
			team_b = [p for p in players if p[2] == 'B']
			# Hands
			cur.execute(
				"""
				SELECT h.id, h.number, h.taker_user_id, u.username, h.contract, h.trump,
				       h.score_team_a, h.score_team_b, h.points_made_team_a, h.points_made_team_b,
				       h.coinche, h.surcoinche, h.capot_team,
				       h.belote_a, h.belote_b, h.general, h.created_at
				FROM hands h LEFT JOIN users u ON u.id = h.taker_user_id
				WHERE h.game_id = ?
				ORDER BY h.number ASC
				""",
				(game_id,),
			)
			hands = cur.fetchall()

		# POST: add a hand if allowed
		if request.method == 'POST':
			if not login_required():
				return redirect(url_for('login'))
			user_id = session.get('user_id')
			# Only participants can add hands and only if game in progress
			if game['state'] != 'en_cours':
				flash("La partie n'est pas en cours.", 'warning')
				return redirect(url_for('game_detail', game_id=game_id))
			with closing(g.db.cursor()) as cur:
				cur.execute("SELECT 1 FROM game_players WHERE game_id = ? AND user_id = ?", (game_id, user_id))
				if not cur.fetchone():
					flash("Seuls les joueurs de la partie peuvent ajouter des manches.", 'danger')
					return redirect(url_for('game_detail', game_id=game_id))
			# Parse form
			try:
				taker_user_id = int(request.form.get('taker_user_id') or 0) or None
				pre_score_a = int(request.form.get('score_team_a') or 0)
				pre_score_b = int(request.form.get('score_team_b') or 0)
			except ValueError:
				flash('Scores invalides.', 'danger')
				return redirect(url_for('game_detail', game_id=game_id))
			contract_raw = (request.form.get('contract') or '').strip()
			trump = (request.form.get('trump') or '').strip() or None
			coinche = 1 if (request.form.get('coinche') == 'on') else 0
			surcoinche = 1 if (request.form.get('surcoinche') == 'on') else 0
			# belotes and general
			try:
				belote_a = int(request.form.get('belote_a') or 0)
				belote_b = int(request.form.get('belote_b') or 0)
			except ValueError:
				flash('Belotes invalides.', 'danger')
				return redirect(url_for('game_detail', game_id=game_id))
			general = 1 if (request.form.get('general') == 'on') else 0
			# Contract validation: either numeric (80..180 step 10) or special values
			special_contracts = {'Capot', 'Générale'}
			contract = None
			if contract_raw:
				if contract_raw in special_contracts:
					contract = contract_raw
				else:
					try:
						c_val = int(contract_raw)
						if c_val < 80 or c_val > 180 or (c_val % 10 != 0):
							raise ValueError()
						contract = str(c_val)
					except ValueError:
						flash('Contrat invalide: choisissez un nombre entre 80 et 180 (pas de 10) ou un contrat spécial.', 'danger')
						return redirect(url_for('game_detail', game_id=game_id))
			# Belote rules per trump
			trump_norm = (trump or '').strip().lower()
			if trump_norm == 'sans atout':
				if belote_a > 0 or belote_b > 0:
					flash('En Sans atout, aucune belote n\'est autorisée.', 'warning')
					return redirect(url_for('game_detail', game_id=game_id))
			elif trump_norm == 'tout atout':
				if (belote_a + belote_b) > 4:
					flash('En Tout atout, il ne peut y avoir que 4 belotes au total (cumulé A+B).', 'warning')
					return redirect(url_for('game_detail', game_id=game_id))
			else:
				if (belote_a + belote_b) > 1:
					flash('Avec un atout couleur, une seule belote au total (A+B) est autorisée.', 'warning')
					return redirect(url_for('game_detail', game_id=game_id))
			# Validate taker belongs to game if provided
			if taker_user_id:
				with closing(g.db.cursor()) as cur:
					cur.execute("SELECT 1 FROM game_players WHERE game_id = ? AND user_id = ?", (game_id, taker_user_id))
					if not cur.fetchone():
						flash("Le preneur doit être un joueur de la partie.", 'danger')
						return redirect(url_for('game_detail', game_id=game_id))
			taker_team = None
			if taker_user_id:
				# players: list of tuples (user_id, username, team, position)
				for p in players:
					if p[0] == taker_user_id:
						taker_team = p[2]
						break
			computed_scores = compute_score({
				"A": {
					"pre_score": pre_score_a,
					"belote": belote_a
				},
				"B": {
					"pre_score": pre_score_b,
					"belote": belote_b
				},
				"coinche": coinche,
				"surcoinche": surcoinche,
				"general": general,
				"taker_team": taker_team,
				"contract": contract,
				"trump": trump
			})
			# compute_score returns a dict with keys 'A' and 'B'
			score_a = int(computed_scores.get("A", 0))
			score_b = int(computed_scores.get("B", 0))
			# Derive capot team from points made (pre-scores)
			capot_team = None
			if pre_score_a == 162 and pre_score_b == 0:
				capot_team = 'A'
			elif pre_score_b == 162 and pre_score_a == 0:
				capot_team = 'B'

			# Next hand number
			with closing(g.db.cursor()) as cur:
				cur.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM hands WHERE game_id = ?", (game_id,))
				number = cur.fetchone()[0]
				now = datetime.utcnow().isoformat(timespec='seconds')
				cur.execute(
					"""
					INSERT INTO hands (game_id, number, taker_user_id, contract, trump,
					  score_team_a, score_team_b, points_made_team_a, points_made_team_b,
					  coinche, surcoinche, capot_team, belote_a, belote_b, general, created_at)
					VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
					""",
					(game_id, number, taker_user_id, contract, trump,
					 score_a, score_b, pre_score_a, pre_score_b,
					 coinche, surcoinche, capot_team, belote_a, belote_b, general, now),
				)
				# Recompute totals and update game
				cur.execute("SELECT COALESCE(SUM(score_team_a),0), COALESCE(SUM(score_team_b),0) FROM hands WHERE game_id = ?", (game_id,))
				totals = cur.fetchone()
				points_a, points_b = int(totals[0]), int(totals[1])
				state = 'en_cours'
				if points_a >= game['target_points'] or points_b >= game['target_points']:
					state = 'terminee'
				cur.execute(
					"UPDATE games SET points_team_a = ?, points_team_b = ?, updated_at = ?, state = ? WHERE id = ?",
					(points_a, points_b, now, state, game_id),
				)
				g.db.commit()
				flash('Manche ajoutée.', 'success')
			return redirect(url_for('game_detail', game_id=game_id))

		# GET render
		return render_template(
			'game_detail.html',
			game=game,
			team_a=team_a,
			team_b=team_b,
			hands=hands,
			can_add_hand=(session.get('user_id') and game['state'] == 'en_cours' and any(p[0] == session.get('user_id') for p in players)),
			players=players,
		)

	@app.route('/games/new', methods=['GET', 'POST'])
	def new_game():
		if not login_required():
			return redirect(url_for('login'))
		if request.method == 'POST':
			try:
				p_a1 = int(request.form.get('team_a_player1') or 0)
				p_a2 = int(request.form.get('team_a_player2') or 0)
				p_b1 = int(request.form.get('team_b_player1') or 0)
				p_b2 = int(request.form.get('team_b_player2') or 0)
			except ValueError:
				flash('Sélection de joueurs invalide.', 'danger')
				return redirect(url_for('new_game'))
			players = [p_a1, p_a2, p_b1, p_b2]
			if any(p <= 0 for p in players) or len(set(players)) != 4:
				flash('Veuillez sélectionner 4 joueurs distincts.', 'danger')
				return redirect(url_for('new_game'))
			# target points
			try:
				target_points = int(request.form.get('target_points') or 1000)
			except ValueError:
				target_points = 1000
			created_by = session.get('user_id')
			if not created_by:
				flash('Session expirée, reconnectez-vous.', 'warning')
				return redirect(url_for('login'))
			now = datetime.utcnow().isoformat(timespec='seconds')
			with closing(g.db.cursor()) as cur:
				cur.execute(
					"INSERT INTO games (created_at, updated_at, created_by, state, points_team_a, points_team_b, target_points) VALUES (?, ?, ?, 'en_cours', 0, 0, ?)",
					(now, now, created_by, target_points),
				)
				game_id = cur.lastrowid
				cur.executemany(
					"INSERT INTO game_players (game_id, user_id, team, position) VALUES (?, ?, ?, ?)",
					[
						(game_id, p_a1, 'A', 1),
						(game_id, p_a2, 'A', 2),
						(game_id, p_b1, 'B', 1),
						(game_id, p_b2, 'B', 2),
					],
				)
				g.db.commit()
			flash('Partie créée.', 'success')
			return redirect(url_for('games_list'))
		with closing(g.db.cursor()) as cur:
			cur.execute("SELECT id, username FROM users WHERE is_active = 1 ORDER BY username")
			users = cur.fetchall()
		if len(users) < 4:
			flash("Vous devez avoir au moins 4 utilisateurs actifs pour créer une partie (utilisez la CLI create-user).", 'warning')
		return render_template('new_game.html', users=users)

	@app.route('/profil')
	def profile():
		if not login_required():
			return redirect(url_for('login'))
		user_id = session.get('user_id')
		username = session.get('user')
		with closing(g.db.cursor()) as cur:
			cur.execute(
				"""
				SELECT g.id,
				       g.created_at,
				       g.updated_at,
				       g.points_team_a,
				       g.points_team_b,
				       g.target_points,
				       (SELECT group_concat(u.username, ', ')
				        FROM game_players gp2 JOIN users u ON u.id = gp2.user_id
				        WHERE gp2.game_id = g.id AND gp2.team = 'A') AS team_a,
				       (SELECT group_concat(u.username, ', ')
				        FROM game_players gp2 JOIN users u ON u.id = gp2.user_id
				        WHERE gp2.game_id = g.id AND gp2.team = 'B') AS team_b
				FROM games g
				WHERE g.state = 'en_cours'
				  AND EXISTS (SELECT 1 FROM game_players gp WHERE gp.game_id = g.id AND gp.user_id = ?)
				ORDER BY g.updated_at DESC
				""",
				(user_id,),
			)
			ongoing = [
				{
					'id': r[0],
					'created_at': r[1],
					'updated_at': r[2],
					'score_a': r[3],
					'score_b': r[4],
					'target_points': r[5],
					'team_a': r[6] or '-',
					'team_b': r[7] or '-',
				}
				for r in cur.fetchall()
			]
		return render_template('profile.html', username=username, ongoing=ongoing)

	# CLI command to (re)initialize the database
	@app.cli.command('init-db')
	def init_db_command():
		init_db(app)
		print('Base de données initialisée.')

	# CLI to create a user
	@app.cli.command('create-user')
	@click.option('--username', prompt=True, help='Nom d\'utilisateur (unique, insensible à la casse)')
	@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Mot de passe')
	def create_user_command(username: str, password: str):
		username = username.strip()
		if not username or not password or len(password) < 8:
			print('Erreur: nom d\'utilisateur et mot de passe (>= 8 caractères) requis.')
			return
		password_hash = generate_password_hash(password, method='pbkdf2:sha256')
		with closing(get_db(app)) as db:
			with closing(db.cursor()) as cur:
				# Check if exists (case-insensitive)
				cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
				if cur.fetchone():
					print('Erreur: cet utilisateur existe déjà.')
					return
				cur.execute(
					"INSERT INTO users (username, password_hash, created_at, is_active) VALUES (?, ?, ?, 1)",
					(username, password_hash, datetime.utcnow().isoformat(timespec='seconds')),
				)
				db.commit()
		print(f"Utilisateur '{username}' créé avec succès.")

	return app


def get_db(app: Flask):
	db = getattr(g, '_database', None)
	if db is None:
		# Ensure parent directory exists
		db_path = app.config['DATABASE']
		db_dir = os.path.dirname(db_path)
		if db_dir and not os.path.exists(db_dir):
			os.makedirs(db_dir, exist_ok=True)
		need_init = not os.path.exists(db_path)
		db = g._database = sqlite3.connect(db_path)
		try:
			db.execute('PRAGMA foreign_keys = ON')
		except Exception:
			pass
		if need_init:
			init_db(app, db)
	return db


def init_db(app: Flask, db: sqlite3.Connection | None = None):
	close_after = False
	if db is None:
		# Ensure parent directory exists when creating DB directly
		db_path = app.config['DATABASE']
		db_dir = os.path.dirname(db_path)
		if db_dir and not os.path.exists(db_dir):
			os.makedirs(db_dir, exist_ok=True)
		db = sqlite3.connect(db_path)
		try:
			db.execute('PRAGMA foreign_keys = ON')
		except Exception:
			pass
		close_after = True
	with closing(db.cursor()) as cur:
		# Users table (create first so FKs can reference it)
		cur.execute(
			'''CREATE TABLE IF NOT EXISTS users (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE COLLATE NOCASE,
				password_hash TEXT NOT NULL,
				created_at TEXT NOT NULL,
				is_active INTEGER NOT NULL DEFAULT 1
			)'''
		)


		# New normalized tables
		cur.execute(
			'''CREATE TABLE IF NOT EXISTS games (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				created_at TEXT NOT NULL,
				updated_at TEXT NOT NULL,
				created_by INTEGER NOT NULL,
				state TEXT NOT NULL CHECK(state IN ('en_cours','terminee','annulee')) DEFAULT 'en_cours',
				points_team_a INTEGER NOT NULL DEFAULT 0,
				points_team_b INTEGER NOT NULL DEFAULT 0,
				target_points INTEGER NOT NULL DEFAULT 1000,
				FOREIGN KEY(created_by) REFERENCES users(id)
			)'''
		)
		cur.execute(
			'''CREATE TABLE IF NOT EXISTS game_players (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				game_id INTEGER NOT NULL,
				user_id INTEGER NOT NULL,
				team TEXT NOT NULL CHECK(team IN ('A','B')),
				position INTEGER,
				FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
				FOREIGN KEY(user_id) REFERENCES users(id)
			)'''
		)
		cur.execute('CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id)')
		cur.execute('CREATE INDEX IF NOT EXISTS idx_game_players_user ON game_players(user_id)')
		cur.execute(
			'''CREATE TABLE IF NOT EXISTS hands (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				game_id INTEGER NOT NULL,
				number INTEGER NOT NULL,
				taker_user_id INTEGER,
				contract TEXT,
				trump TEXT,
				score_team_a INTEGER NOT NULL DEFAULT 0,
				score_team_b INTEGER NOT NULL DEFAULT 0,
				points_made_team_a INTEGER NOT NULL DEFAULT 0,
				points_made_team_b INTEGER NOT NULL DEFAULT 0,
				coinche INTEGER NOT NULL DEFAULT 0,
				surcoinche INTEGER NOT NULL DEFAULT 0,
				capot_team TEXT,
				belote_a INTEGER NOT NULL DEFAULT 0,
				belote_b INTEGER NOT NULL DEFAULT 0,
				general INTEGER NOT NULL DEFAULT 0,
				created_at TEXT NOT NULL,
				FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
				FOREIGN KEY(taker_user_id) REFERENCES users(id)
			)'''
		)
		# Ensure target_points column exists if DB was created before this field
		cur.execute("PRAGMA table_info('games')")
		cols = [c[1] for c in cur.fetchall()]
		if 'target_points' not in cols:
			cur.execute("ALTER TABLE games ADD COLUMN target_points INTEGER NOT NULL DEFAULT 1000")
		# Ensure new hand columns exist if DB was created before these fields
		cur.execute("PRAGMA table_info('hands')")
		h_cols = [c[1] for c in cur.fetchall()]
		if 'belote_a' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN belote_a INTEGER NOT NULL DEFAULT 0")
		if 'belote_b' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN belote_b INTEGER NOT NULL DEFAULT 0")
		if 'general' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN general INTEGER NOT NULL DEFAULT 0")
		if 'points_made_team_a' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN points_made_team_a INTEGER NOT NULL DEFAULT 0")
		if 'points_made_team_b' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN points_made_team_b INTEGER NOT NULL DEFAULT 0")
		if 'capot_team' not in h_cols:
			cur.execute("ALTER TABLE hands ADD COLUMN capot_team TEXT")
		db.commit()
	if close_after:
		db.close()


if __name__ == '__main__':
	app = create_app()
	app.run(host=app.config.get('HOST', '0.0.0.0'), port=app.config.get('PORT', 5000), debug=app.config.get('DEBUG', True))


import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import click

from db.core import get_db
from db.schema import init_db
from db import users as users_repo
from db import games as games_repo
from db import hands as hands_repo

from services.scores import compute_score
from services.get_day_heatmap import get_day_heatmap
from services.statistics import (
    get_global_statistics,
    get_player_statistics,
    get_contract_statistics,
    get_trump_statistics,
    get_special_events_statistics,
    get_player_vs_player_statistics,
    get_player_taking_statistics,
    get_score_distribution,
    get_team_performance
)
from services.duo_ranking import get_duo_rankings

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
	app.config.setdefault('PERMANENT_SESSION_LIFETIME', timedelta(days=1))

	# Duo ranking configuration (server-side, overridable via env)
	def _get_float_env(name: str, default: float) -> float:
		try:
			return float(os.environ.get(name, default))
		except Exception:
			return float(default)

	def _get_int_env(name: str, default: int) -> int:
		try:
			return int(os.environ.get(name, default))
		except Exception:
			return int(default)

	app.config['DUO_RANKING_ALPHA'] = _get_float_env('DUO_RANKING_ALPHA', 2.0)
	app.config['DUO_RANKING_LAMBDA'] = _get_float_env('DUO_RANKING_LAMBDA', -0.1)
	app.config['DUO_RANKING_K'] = _get_float_env('DUO_RANKING_K', 0.3)
	app.config['DUO_RANKING_A'] = _get_float_env('DUO_RANKING_A', 100.0)
	app.config['DUO_RANKING_B'] = _get_float_env('DUO_RANKING_B', 100.0)
	app.config['DUO_RANKING_MIN_GAMES'] = _get_int_env('DUO_RANKING_MIN_GAMES', 1)
	app.config['DUO_RANKING_LIMIT'] = _get_int_env('DUO_RANKING_LIMIT', 50)

	@app.before_request
	def before_request():
		g.db = get_db(app)

	@app.teardown_request
	def teardown_request(exception):
		db = getattr(g, 'db', None)
		if db is not None:
			db.close()

	# Register Jinja filter for French datetime formatting
	def fr_datetime(value):
		if not value:
			return ''
		try:
			if isinstance(value, str):
				val = value.replace('T', ' ')
				dt = datetime.fromisoformat(val)
			else:
				dt = value
			return dt.strftime('%d/%m/%Y %H:%M')
		except Exception:
			return str(value).replace('T', ' ')

	app.jinja_env.filters['fr_datetime'] = fr_datetime

	# ----- Routes -----
	@app.route('/')
	def index():
		return render_template('index.html', heatmap_data=get_day_heatmap(g.db))

	@app.route('/login', methods=['GET', 'POST'])
	def login():
		if request.method == 'POST':
			username = request.form.get('username', '').strip()
			password = request.form.get('password', '').strip()
			if not username or not password:
				flash('Identifiants invalides.', 'danger')
				return render_template('login.html')

			row = users_repo.find_user_by_username(g.db, username)
			if row and check_password_hash(row[2], password):
				if(not(row[3])):
					flash('Votre compte est en cours de validation', 'success')
					return render_template('login.html')
				session.permanent = True
				session.clear()
				session['user_id'] = row[0]
				session['user'] = row[1]
				session['is_admin'] = bool(row[4]) if len(row) > 4 else False
				flash('Connexion réussie.', 'success')
				return redirect(url_for('index'))
		
			flash('Identifiants invalides.', 'danger')
		return render_template('login.html')

	@app.route('/register', methods=['GET', 'POST'])
	def register():
		if request.method == 'POST':
			username = request.form.get('username', '').strip()
			password = request.form.get('password', '').strip()
			password_confirm = request.form.get('password_confirm', '').strip()
			
			if not username or not password:
				flash('Nom d\'utilisateur et mot de passe requis.', 'danger')
				return render_template('register.html')
			
			if len(password) < 8:
				flash('Le mot de passe doit contenir au moins 8 caractères.', 'danger')
				return render_template('register.html')
			
			if password != password_confirm:
				flash('Les mots de passe ne correspondent pas.', 'danger')
				return render_template('register.html')
			
			existing_user = users_repo.find_user_by_username(g.db, username)
			if existing_user:
				flash('Ce nom d\'utilisateur est déjà pris.', 'danger')
				return render_template('register.html')
			
			password_hash = generate_password_hash(password, method='pbkdf2:sha256')
			now = datetime.utcnow().isoformat(timespec='seconds')
			user_id = users_repo.create_inactive_user(g.db, username, password_hash, now)
			
			if user_id:
				flash('Compte créé avec succès ! Votre compte doit être activé par un administrateur avant de pouvoir vous connecter.', 'info')
				return redirect(url_for('login'))
			else:
				flash('Erreur lors de la création du compte.', 'danger')
				return render_template('register.html')
		
		return render_template('register.html')

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

	def admin_required():
		if not session.get('user') or not session.get('is_admin'):
			flash('Accès administrateur requis.', 'danger')
			return False
		return True

	@app.route('/games')
	def games_list():
		rows = games_repo.list_games(g.db)
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
			for r in rows
		]
		return render_template('games.html', games=games)

	@app.route('/games/<int:game_id>', methods=['GET', 'POST'])
	def game_detail(game_id: int):
		game_row = games_repo.load_game_basics(g.db, game_id)
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
		players = games_repo.load_players(g.db, game_id)
		team_a = [p for p in players if p[2] == 'A']
		team_b = [p for p in players if p[2] == 'B']
		hands = hands_repo.list_hands(g.db, game_id)

		if request.method == 'POST':
			if not login_required():
				return redirect(url_for('login'))
			user_id = session.get('user_id')
			if game['state'] != 'en_cours':
				flash("La partie n'est pas en cours.", 'warning')
				return redirect(url_for('game_detail', game_id=game_id))
			if not games_repo.is_participant(g.db, game_id, user_id):
				flash("Seuls les joueurs de la partie peuvent ajouter des manches.", 'danger')
				return redirect(url_for('game_detail', game_id=game_id))
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
			try:
				belote_a = int(request.form.get('belote_a') or 0)
				belote_b = int(request.form.get('belote_b') or 0)
			except ValueError:
				flash('Belotes invalides.', 'danger')
				return redirect(url_for('game_detail', game_id=game_id))
			general = 1 if (request.form.get('general') == 'on') else 0
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
			if taker_user_id and not games_repo.is_participant(g.db, game_id, taker_user_id):
				flash("Le preneur doit être un joueur de la partie.", 'danger')
				return redirect(url_for('game_detail', game_id=game_id))
			taker_team = None
			if taker_user_id:
				for p in players:
					if p[0] == taker_user_id:
						taker_team = p[2]
						break
			if not contract:
				flash('Veuillez choisir un contrat.', 'warning')
				return redirect(url_for('game_detail', game_id=game_id))
			if not taker_team:
				flash('Veuillez choisir un preneur.', 'warning')
				return redirect(url_for('game_detail', game_id=game_id))
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
			score_a = int(computed_scores.get("A", 0))
			score_b = int(computed_scores.get("B", 0))
			capot_team = None
			if pre_score_a == 162 and pre_score_b == 0:
				capot_team = 'A'
			elif pre_score_b == 162 and pre_score_a == 0:
				capot_team = 'B'

			number = hands_repo.next_hand_number(g.db, game_id)
			now = datetime.utcnow().isoformat(timespec='seconds')
			hands_repo.insert_hand(
				g.db, game_id, number, taker_user_id, contract, trump,
				score_a, score_b, pre_score_a, pre_score_b,
				coinche, surcoinche, capot_team, belote_a, belote_b, general, now
			)
			games_repo.recompute_totals_and_update_game(g.db, game_id, game['target_points'], now)
			flash('Manche ajoutée.', 'success')
			return redirect(url_for('game_detail', game_id=game_id))

		user_id = session.get('user_id')
		is_participant = user_id and any(p[0] == user_id for p in players)
		return render_template(
			'game_detail.html',
			game=game,
			team_a=team_a,
			team_b=team_b,
			hands=hands,
			can_add_hand=(user_id and game['state'] == 'en_cours' and is_participant),
			is_participant=is_participant,
			players=players,
		)

	@app.route('/games/<int:game_id>/hands/<int:hand_id>/delete', methods=['POST'])
	def delete_hand(game_id: int, hand_id: int):
		if not session.get('user_id'):
			flash('Veuillez vous connecter pour continuer.', 'warning')
			return redirect(url_for('login'))
		user_id = session.get('user_id')
		if not games_repo.is_participant(g.db, game_id, user_id):
			flash("Action non autorisée.", 'danger')
			return redirect(url_for('game_detail', game_id=game_id))
		h = hands_repo.get_hand(g.db, hand_id)
		if not h or h[1] != game_id:
			flash("Manche introuvable.", 'warning')
			return redirect(url_for('game_detail', game_id=game_id))
		hands_repo.delete_hand(g.db, hand_id)
		now = datetime.utcnow().isoformat(timespec='seconds')
		games_repo.recompute_totals_and_update_game(g.db, game_id, games_repo.load_game_basics(g.db, game_id)[7], now)
		flash('Manche supprimée.', 'info')
		return redirect(url_for('game_detail', game_id=game_id))

	@app.route('/games/<int:game_id>/update_target', methods=['POST'])
	def update_target_points(game_id: int):
		if not session.get('user_id'):
			flash('Veuillez vous connecter pour continuer.', 'warning')
			return redirect(url_for('login'))
		user_id = session.get('user_id')
		if not games_repo.is_participant(g.db, game_id, user_id):
			flash("Seuls les membres de la partie peuvent modifier l'objectif.", 'danger')
			return redirect(url_for('game_detail', game_id=game_id))
		
		try:
			new_target = int(request.form.get('target_points', 1000))
			if new_target < 100:
				flash("L'objectif doit être d'au moins 100 points.", 'warning')
				return redirect(url_for('game_detail', game_id=game_id))
		except ValueError:
			flash("Valeur d'objectif invalide.", 'danger')
			return redirect(url_for('game_detail', game_id=game_id))
		
		now = datetime.utcnow().isoformat(timespec='seconds')
		success = games_repo.update_target_points(g.db, game_id, new_target, now)
		
		if success:
			flash('Objectif de points modifié avec succès.', 'success')
		else:
			flash('Erreur lors de la modification de l\'objectif.', 'danger')
		
		return redirect(url_for('game_detail', game_id=game_id))


	@app.route('/games/<int:game_id>/hands/<int:hand_id>/edit', methods=['GET', 'POST'])
	def edit_hand(game_id: int, hand_id: int):
		if not session.get('user_id'):
			flash('Veuillez vous connecter pour continuer.', 'warning')
			return redirect(url_for('login'))
		user_id = session.get('user_id')
		if not games_repo.is_participant(g.db, game_id, user_id):
			flash("Action non autorisée.", 'danger')
			return redirect(url_for('game_detail', game_id=game_id))
		game_row = games_repo.load_game_basics(g.db, game_id)
		if not game_row:
			flash('Partie introuvable.', 'warning')
			return redirect(url_for('games_list'))
		hand = hands_repo.get_hand(g.db, hand_id)
		if not hand or hand[1] != game_id:
			flash('Manche introuvable.', 'warning')
			return redirect(url_for('game_detail', game_id=game_id))
		players = games_repo.load_players(g.db, game_id)
		if request.method == 'POST':
			try:
				taker_user_id = int(request.form.get('taker_user_id') or 0) or None
				pre_score_a = int(request.form.get('score_team_a') or 0)
				pre_score_b = int(request.form.get('score_team_b') or 0)
			except ValueError:
				flash('Scores invalides.', 'danger')
				return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			contract_raw = (request.form.get('contract') or '').strip()
			trump = (request.form.get('trump') or '').strip() or None
			coinche = 1 if (request.form.get('coinche') == 'on') else 0
			surcoinche = 1 if (request.form.get('surcoinche') == 'on') else 0
			try:
				belote_a = int(request.form.get('belote_a') or 0)
				belote_b = int(request.form.get('belote_b') or 0)
			except ValueError:
				flash('Belotes invalides.', 'danger')
				return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			general = 1 if (request.form.get('general') == 'on') else 0
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
						return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			trump_norm = (trump or '').strip().lower()
			if trump_norm == 'sans atout':
				if belote_a > 0 or belote_b > 0:
					flash('En Sans atout, aucune belote n\'est autorisée.', 'warning')
					return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			elif trump_norm == 'tout atout':
				if (belote_a + belote_b) > 4:
					flash('En Tout atout, il ne peut y avoir que 4 belotes au total (cumulé A+B).', 'warning')
					return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			else:
				if (belote_a + belote_b) > 1:
					flash('Avec un atout couleur, une seule belote au total (A+B) est autorisée.', 'warning')
					return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			taker_team = None
			if taker_user_id:
				for p in players:
					if p[0] == taker_user_id:
						taker_team = p[2]
						break
			if not contract:
				flash('Veuillez choisir un contrat.', 'warning')
				return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			if not taker_team:
				flash('Veuillez choisir un preneur.', 'warning')
				return redirect(url_for('edit_hand', game_id=game_id, hand_id=hand_id))
			computed = compute_score({
				"A": {"pre_score": pre_score_a, "belote": belote_a},
				"B": {"pre_score": pre_score_b, "belote": belote_b},
				"coinche": coinche,
				"surcoinche": surcoinche,
				"general": general,
				"taker_team": taker_team,
				"contract": contract,
				"trump": trump,
			})
			score_a = int(computed.get("A", 0))
			score_b = int(computed.get("B", 0))
			capot_team = None
			if pre_score_a == 162 and pre_score_b == 0:
				capot_team = 'A'
			elif pre_score_b == 162 and pre_score_a == 0:
				capot_team = 'B'
			hands_repo.update_hand(
				g.db, hand_id, taker_user_id, contract, trump,
				score_a, score_b, pre_score_a, pre_score_b,
				coinche, surcoinche, capot_team, belote_a, belote_b, general
			)
			now = datetime.utcnow().isoformat(timespec='seconds')
			games_repo.recompute_totals_and_update_game(g.db, game_id, game_row[7], now)
			flash('Manche modifiée.', 'success')
			return redirect(url_for('game_detail', game_id=game_id))
		players = games_repo.load_players(g.db, game_id)
		return render_template('edit_hand.html', game_id=game_id, hand=hand, players=players)

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
			try:
				target_points = int(request.form.get('target_points') or 1000)
			except ValueError:
				target_points = 1000
			created_by = session.get('user_id')
			if not created_by:
				flash('Session expirée, reconnectez-vous.', 'warning')
				return redirect(url_for('login'))
			now = datetime.utcnow().isoformat(timespec='seconds')
			games_repo.create_game(g.db, created_by, target_points, players, now)
			flash('Partie créée.', 'success')
			return redirect(url_for('games_list'))
		users = users_repo.get_active_users(g.db)
		if len(users) < 4:
			flash("Vous devez avoir au moins 4 utilisateurs actifs pour créer une partie (utilisez la CLI create-user).", 'warning')
		return render_template('new_game.html', users=users)

	@app.route('/profil')
	def profile():
		if not login_required():
			return redirect(url_for('login'))
		user_id = session.get('user_id')
		username = session.get('user')
		rows = games_repo.list_ongoing_games_for_user(g.db, user_id)
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
			for r in rows
		]
		from services.statistics import get_player_statistics, get_player_vs_player_statistics, get_player_taking_statistics
		player_stats = get_player_statistics(g.db)
		personal_stats = get_player_vs_player_statistics(g.db, user_id)
		taking_stats = get_player_taking_statistics(g.db)

		my_stats = next((p for p in player_stats if p['user_id'] == user_id), None)
		my_taking_stats = next((t for t in taking_stats if t['user_id'] == user_id), None)

		return render_template(
			'profile.html',
			username=username,
			ongoing=ongoing,
			my_stats=my_stats,
			my_taking_stats=my_taking_stats,
			personal_stats=personal_stats
		)

	@app.route('/statistiques')
	def statistics():
		global_stats = get_global_statistics(g.db)
		player_stats = get_player_statistics(g.db)
		contract_stats = get_contract_statistics(g.db)
		trump_stats = get_trump_statistics(g.db)
		special_events = get_special_events_statistics(g.db)
		taking_stats = get_player_taking_statistics(g.db)
		score_dist = get_score_distribution(g.db)
		team_perf = get_team_performance(g.db)
		duo_rankings = get_duo_rankings(
			g.db,
			alpha=app.config['DUO_RANKING_ALPHA'],
			lambda_=app.config['DUO_RANKING_LAMBDA'],
			k=app.config['DUO_RANKING_K'],
			A=app.config['DUO_RANKING_A'],
			B=app.config['DUO_RANKING_B'],
			min_games=app.config['DUO_RANKING_MIN_GAMES'],
			limit=app.config['DUO_RANKING_LIMIT'],
		)
		
		personal_stats = None
		if session.get('user_id'):
			personal_stats = get_player_vs_player_statistics(g.db, session.get('user_id'))
		
		return render_template(
			'statistics.html',
			global_stats=global_stats,
			player_stats=player_stats,
			contract_stats=contract_stats,
			trump_stats=trump_stats,
			special_events=special_events,
			taking_stats=taking_stats,
			score_dist=score_dist,
			team_perf=team_perf,
			duo_rankings=duo_rankings,
			personal_stats=personal_stats
		)

	@app.route('/admin')
	def admin_panel():
		if not admin_required():
			return redirect(url_for('index'))
		users = users_repo.list_all_users(g.db)
		return render_template('admin.html', users=users)

	@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
	def toggle_user(user_id: int):
		if not admin_required():
			return redirect(url_for('index'))
		success = users_repo.toggle_user_status(g.db, user_id)
		if success:
			flash('Statut utilisateur modifié.', 'success')
		else:
			flash('Erreur lors de la modification.', 'danger')
		return redirect(url_for('admin_panel'))

	@app.route('/admin/delete_game/<int:game_id>', methods=['POST'])
	def delete_game(game_id: int):
		if not admin_required():
			return redirect(url_for('index'))
		
		game_row = games_repo.load_game_basics(g.db, game_id)
		if not game_row:
			flash('Partie introuvable.', 'warning')
			return redirect(url_for('games_list'))
		
		success = games_repo.delete_game(g.db, game_id)
		if success:
			flash('Partie supprimée avec succès.', 'success')
		else:
			flash('Erreur lors de la suppression de la partie.', 'danger')
		
		return redirect(url_for('games_list'))

	@app.cli.command('init-db')
	def init_db_command():
		init_db(app)
		print('Base de données initialisée.')

	@app.cli.command('create-user')
	@click.option('--username', prompt=True, help='Nom d\'utilisateur (unique, insensible à la casse)')
	@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Mot de passe')
	@click.option('--admin', is_flag=True, help='Créer un utilisateur administrateur')
	def create_user_command(username: str, password: str, admin: bool):
		username = username.strip()
		if not username or not password or len(password) < 8:
			print('Erreur: nom d\'utilisateur et mot de passe (>= 8 caractères) requis.')
			return
		password_hash = generate_password_hash(password, method='pbkdf2:sha256')
		with get_db(app) as db:
			user_id = users_repo.create_user_with_admin(db, username, password_hash, datetime.utcnow().isoformat(timespec='seconds'), admin)
			if user_id is None:
				print('Erreur: cet utilisateur existe déjà.')
				return
		admin_status = " (administrateur)" if admin else ""
		print(f"Utilisateur '{username}'{admin_status} créé avec succès.")

	return app


if __name__ == '__main__':
	app = create_app()
	app.run(host=app.config.get('HOST', '0.0.0.0'), port=app.config.get('PORT', 5000), debug=app.config.get('DEBUG', True))

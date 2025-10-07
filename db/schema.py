import os
import sqlite3
from contextlib import closing


def init_db(app, db: sqlite3.Connection | None = None):
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
        # Users
        cur.execute(
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )'''
        )

        # Games
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

        # Game players
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

        # Hands
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

        # Migrations
        cur.execute("PRAGMA table_info('games')")
        cols = [c[1] for c in cur.fetchall()]
        if 'target_points' not in cols:
            cur.execute("ALTER TABLE games ADD COLUMN target_points INTEGER NOT NULL DEFAULT 1000")

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

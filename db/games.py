from contextlib import closing


def list_games(db):
    with closing(db.cursor()) as cur:
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
        return cur.fetchall()


def create_game(db, created_by: int, target_points: int, players: list[int], now: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "INSERT INTO games (created_at, updated_at, created_by, state, points_team_a, points_team_b, target_points) VALUES (?, ?, ?, 'en_cours', 0, 0, ?)",
            (now, now, created_by, target_points),
        )
        game_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO game_players (game_id, user_id, team, position) VALUES (?, ?, ?, ?)",
            [
                (game_id, players[0], 'A', 1),
                (game_id, players[1], 'A', 2),
                (game_id, players[2], 'B', 1),
                (game_id, players[3], 'B', 2),
            ],
        )
        db.commit()
        return game_id


def load_game_basics(db, game_id: int):
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, created_at, updated_at, created_by, state, points_team_a, points_team_b, target_points FROM games WHERE id = ?",
            (game_id,),
        )
        return cur.fetchone()


def load_players(db, game_id: int):
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT gp.user_id, u.username, gp.team, gp.position FROM game_players gp JOIN users u ON u.id = gp.user_id WHERE gp.game_id = ? ORDER BY gp.team, gp.position",
            (game_id,),
        )
        return cur.fetchall()


def is_participant(db, game_id: int, user_id: int) -> bool:
    with closing(db.cursor()) as cur:
        cur.execute("SELECT 1 FROM game_players WHERE game_id = ? AND user_id = ?", (game_id, user_id))
        return cur.fetchone() is not None


def recompute_totals_and_update_game(db, game_id: int, target: int, now: str):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT COALESCE(SUM(score_team_a),0), COALESCE(SUM(score_team_b),0) FROM hands WHERE game_id = ?", (game_id,))
        totals = cur.fetchone()
        points_a, points_b = int(totals[0]), int(totals[1])
        state = 'en_cours'
        if points_a >= target or points_b >= target:
            state = 'terminee'
        cur.execute(
            "UPDATE games SET points_team_a = ?, points_team_b = ?, updated_at = ?, state = ? WHERE id = ?",
            (points_a, points_b, now, state, game_id),
        )
        db.commit()
        return points_a, points_b, state


def list_ongoing_games_for_user(db, user_id: int):
    """Return ongoing games where the given user participates.

    Rows contain: id, created_at, updated_at, points_team_a, points_team_b, target_points, team_a, team_b
    """
    with closing(db.cursor()) as cur:
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
        return cur.fetchall()


def delete_game(db, game_id: int):
    """Delete a game and all associated data (hands, players)"""
    try:
        with closing(db.cursor()) as cur:
            cur.execute('DELETE FROM hands WHERE game_id = ?', (game_id,))
            cur.execute('DELETE FROM game_players WHERE game_id = ?', (game_id,))
            cur.execute('DELETE FROM games WHERE id = ?', (game_id,))
            
            db.commit()
            return cur.rowcount > 0
    except Exception:
        db.rollback()
        return False


def get_games_count_by_day(db, year: int, month: int):
    """Get the count of games created by day for a specific month/year
    
    Returns a dictionary with day numbers as keys and game counts as values
    """
    with closing(db.cursor()) as cur:
        date_pattern = f"{year:04d}-{month:02d}-%"
        
        cur.execute(
            """
            SELECT 
                CAST(SUBSTR(created_at, 9, 2) AS INTEGER) as day,
                COUNT(*) as game_count
            FROM games 
            WHERE created_at LIKE ?
            GROUP BY SUBSTR(created_at, 9, 2)
            ORDER BY day
            """,
            (date_pattern,)
        )
        
        results = cur.fetchall()
        
        return {day: count for day, count in results}


def update_target_points(db, game_id: int, new_target: int, now: str):
    """Update the target points for a game and recompute its state.
    
    If the game was finished and the new target is higher than both team scores,
    it will be set back to 'en_cours'.
    """
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT points_team_a, points_team_b, state FROM games WHERE id = ?",
            (game_id,)
        )
        row = cur.fetchone()
        if not row:
            return False
        
        points_a, points_b, current_state = row
        
        new_state = 'en_cours'
        if points_a >= new_target or points_b >= new_target:
            new_state = 'terminee'
        
        cur.execute(
            "UPDATE games SET target_points = ?, state = ?, updated_at = ? WHERE id = ?",
            (new_target, new_state, now, game_id)
        )
        
        db.commit()
        return True

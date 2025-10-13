"""Service pour calculer les statistiques du jeu de Contrée"""
from contextlib import closing


def get_global_statistics(db):
    """Récupère les statistiques globales de toutes les parties"""
    stats = {}
    
    with closing(db.cursor()) as cur:
        cur.execute("SELECT COUNT(*) FROM games")
        stats['total_games'] = cur.fetchone()[0]
        
        cur.execute("SELECT state, COUNT(*) FROM games GROUP BY state")
        stats['games_by_state'] = {row[0]: row[1] for row in cur.fetchall()}
        
        cur.execute("SELECT COUNT(*) FROM hands")
        stats['total_hands'] = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        stats['total_active_users'] = cur.fetchone()[0]
        
        cur.execute("""
            SELECT AVG(hand_count) 
            FROM (SELECT game_id, COUNT(*) as hand_count FROM hands GROUP BY game_id)
        """)
        result = cur.fetchone()[0]
        stats['avg_hands_per_game'] = round(result, 2) if result else 0
        
        cur.execute("SELECT AVG(points_team_a + points_team_b) FROM games WHERE state = 'terminee'")
        result = cur.fetchone()[0]
        stats['avg_total_points'] = round(result, 2) if result else 0
        
    return stats


def get_player_statistics(db):
    """Récupère les statistiques par joueur"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT 
                u.id,
                u.username,
                COUNT(DISTINCT gp.game_id) as games_played,
                SUM(CASE WHEN g.state = 'terminee' THEN 1 ELSE 0 END) as games_finished,
                SUM(CASE 
                    WHEN g.state = 'terminee' AND gp.team = 'A' AND g.points_team_a > g.points_team_b THEN 1
                    WHEN g.state = 'terminee' AND gp.team = 'B' AND g.points_team_b > g.points_team_a THEN 1
                    ELSE 0
                END) as games_won,
                SUM(CASE 
                    WHEN gp.team = 'A' THEN g.points_team_a
                    WHEN gp.team = 'B' THEN g.points_team_b
                    ELSE 0
                END) as total_points_scored
            FROM users u
            LEFT JOIN game_players gp ON gp.user_id = u.id
            LEFT JOIN games g ON g.id = gp.game_id
            WHERE u.is_active = 1
            GROUP BY u.id, u.username
            ORDER BY games_won DESC, games_played DESC
        """)
        
        players = []
        for row in cur.fetchall():
            user_id, username, games_played, games_finished, games_won, total_points = row
            win_rate = round((games_won / games_finished * 100), 2) if games_finished > 0 else 0
            avg_points = round(total_points / games_played, 2) if games_played > 0 else 0
            
            players.append({
                'user_id': user_id,
                'username': username,
                'games_played': games_played or 0,
                'games_finished': games_finished or 0,
                'games_won': games_won or 0,
                'win_rate': win_rate,
                'total_points_scored': total_points or 0,
                'avg_points_per_game': avg_points
            })
        
        return players


def get_contract_statistics(db):
    """Récupère les statistiques sur les contrats"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT contract, COUNT(*) as count
            FROM hands
            WHERE contract IS NOT NULL
            GROUP BY contract
            ORDER BY contract
        """)
        contracts_distribution = {row[0]: row[1] for row in cur.fetchall()}
        
        cur.execute("""
            SELECT 
                h.contract,
                COUNT(*) as total,
                SUM(CASE 
                    WHEN gp.team = 'A' AND h.points_made_team_a >= CAST(h.contract AS INTEGER) THEN 1
                    WHEN gp.team = 'B' AND h.points_made_team_b >= CAST(h.contract AS INTEGER) THEN 1
                    ELSE 0
                END) as success
            FROM hands h
            JOIN game_players gp ON gp.user_id = h.taker_user_id AND gp.game_id = h.game_id
            WHERE h.contract NOT IN ('Capot', 'Générale')
              AND h.contract IS NOT NULL
            GROUP BY h.contract
            ORDER BY h.contract
        """)
        
        contract_success = []
        for row in cur.fetchall():
            contract, total, success = row
            success_rate = round((success / total * 100), 2) if total > 0 else 0
            contract_success.append({
                'contract': contract,
                'total': total,
                'success': success,
                'success_rate': success_rate
            })
        
        return {
            'distribution': contracts_distribution,
            'success_rates': contract_success
        }


def get_trump_statistics(db):
    """Récupère les statistiques sur les atouts"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT trump, COUNT(*) as count
            FROM hands
            WHERE trump IS NOT NULL
            GROUP BY trump
            ORDER BY count DESC
        """)
        trump_distribution = {row[0]: row[1] for row in cur.fetchall()}
        
        cur.execute("""
            SELECT 
                trump,
                AVG(points_made_team_a + points_made_team_b) as avg_points
            FROM hands
            WHERE trump IS NOT NULL
            GROUP BY trump
            ORDER BY avg_points DESC
        """)
        trump_avg_points = {row[0]: round(row[1], 2) for row in cur.fetchall()}
        
        return {
            'distribution': trump_distribution,
            'avg_points': trump_avg_points
        }


def get_special_events_statistics(db):
    """Récupère les statistiques sur les événements spéciaux"""
    with closing(db.cursor()) as cur:
        cur.execute("SELECT COUNT(*) FROM hands WHERE coinche = 1")
        coinches = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM hands WHERE surcoinche = 1")
        surcoinches = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM hands WHERE capot_team IS NOT NULL")
        capots = cur.fetchone()[0]
        
        cur.execute("""
            SELECT capot_team, COUNT(*) as count
            FROM hands
            WHERE capot_team IS NOT NULL
            GROUP BY capot_team
        """)
        capots_by_team = {row[0]: row[1] for row in cur.fetchall()}
        
        cur.execute("SELECT COUNT(*) FROM hands WHERE general = 1")
        generales = cur.fetchone()[0]
        
        cur.execute("SELECT SUM(belote_a + belote_b) FROM hands")
        total_belotes = cur.fetchone()[0] or 0
        
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE 
                    WHEN gp.team = 'A' AND h.score_team_a > h.score_team_b THEN 1
                    WHEN gp.team = 'B' AND h.score_team_b > h.score_team_a THEN 1
                    ELSE 0
                END) as success
            FROM hands h
            JOIN game_players gp ON gp.user_id = h.taker_user_id AND gp.game_id = h.game_id
            WHERE h.coinche = 1
        """)
        coinche_stats = cur.fetchone()
        coinche_total, coinche_success = coinche_stats if coinche_stats else (0, 0)
        coinche_success_rate = round((coinche_success / coinche_total * 100), 2) if coinche_total > 0 else 0
        
        return {
            'coinches': coinches,
            'surcoinches': surcoinches,
            'capots': capots,
            'capots_by_team': capots_by_team,
            'generales': generales,
            'total_belotes': total_belotes,
            'coinche_success_rate': coinche_success_rate
        }


def get_player_vs_player_statistics(db, user_id):
    """Récupère les statistiques d'un joueur contre d'autres joueurs"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT 
                u2.id,
                u2.username,
                COUNT(DISTINCT g.id) as games_played,
                SUM(CASE 
                    WHEN g.state = 'terminee' AND gp1.team = 'A' AND gp2.team = 'B' AND g.points_team_a > g.points_team_b THEN 1
                    WHEN g.state = 'terminee' AND gp1.team = 'B' AND gp2.team = 'A' AND g.points_team_b > g.points_team_a THEN 1
                    ELSE 0
                END) as wins,
                SUM(CASE 
                    WHEN g.state = 'terminee' AND gp1.team = 'A' AND gp2.team = 'B' AND g.points_team_a < g.points_team_b THEN 1
                    WHEN g.state = 'terminee' AND gp1.team = 'B' AND gp2.team = 'A' AND g.points_team_b < g.points_team_a THEN 1
                    ELSE 0
                END) as losses
            FROM game_players gp1
            JOIN games g ON g.id = gp1.game_id
            JOIN game_players gp2 ON gp2.game_id = g.id AND gp2.team != gp1.team
            JOIN users u2 ON u2.id = gp2.user_id
            WHERE gp1.user_id = ?
              AND g.state = 'terminee'
            GROUP BY u2.id, u2.username
            ORDER BY wins DESC, games_played DESC
        """, (user_id,))
        
        opponents = []
        for row in cur.fetchall():
            opp_id, opp_name, games, wins, losses = row
            win_rate = round((wins / games * 100), 2) if games > 0 else 0
            opponents.append({
                'opponent_id': opp_id,
                'opponent_name': opp_name,
                'games_played': games,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate
            })
        
        cur.execute("""
            SELECT 
                u2.id,
                u2.username,
                COUNT(DISTINCT g.id) as games_played,
                SUM(CASE 
                    WHEN g.state = 'terminee' AND gp1.team = 'A' AND g.points_team_a > g.points_team_b THEN 1
                    WHEN g.state = 'terminee' AND gp1.team = 'B' AND g.points_team_b > g.points_team_a THEN 1
                    ELSE 0
                END) as wins
            FROM game_players gp1
            JOIN games g ON g.id = gp1.game_id
            JOIN game_players gp2 ON gp2.game_id = g.id AND gp2.team = gp1.team AND gp2.user_id != gp1.user_id
            JOIN users u2 ON u2.id = gp2.user_id
            WHERE gp1.user_id = ?
              AND g.state = 'terminee'
            GROUP BY u2.id, u2.username
            ORDER BY wins DESC, games_played DESC
        """, (user_id,))
        
        partners = []
        for row in cur.fetchall():
            partner_id, partner_name, games, wins = row
            win_rate = round((wins / games * 100), 2) if games > 0 else 0
            partners.append({
                'partner_id': partner_id,
                'partner_name': partner_name,
                'games_played': games,
                'wins': wins,
                'win_rate': win_rate
            })
        
        return {
            'opponents': opponents,
            'partners': partners
        }


def get_player_taking_statistics(db):
    """Récupère les statistiques sur les preneurs"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT 
                u.id,
                u.username,
                COUNT(*) as times_taken,
                SUM(CASE 
                    WHEN gp.team = 'A' AND h.points_made_team_a >= CAST(CASE WHEN h.contract IN ('Capot', 'Générale') THEN '162' ELSE h.contract END AS INTEGER) THEN 1
                    WHEN gp.team = 'B' AND h.points_made_team_b >= CAST(CASE WHEN h.contract IN ('Capot', 'Générale') THEN '162' ELSE h.contract END AS INTEGER) THEN 1
                    ELSE 0
                END) as contracts_made,
                AVG(CASE 
                    WHEN gp.team = 'A' THEN h.points_made_team_a
                    WHEN gp.team = 'B' THEN h.points_made_team_b
                    ELSE 0
                END) as avg_points_made
            FROM hands h
            JOIN users u ON u.id = h.taker_user_id
            JOIN game_players gp ON gp.user_id = h.taker_user_id AND gp.game_id = h.game_id
            WHERE h.taker_user_id IS NOT NULL
            GROUP BY u.id, u.username
            HAVING times_taken > 0
            ORDER BY contracts_made DESC, times_taken DESC
        """)
        
        takers = []
        for row in cur.fetchall():
            user_id, username, times_taken, contracts_made, avg_points = row
            success_rate = round((contracts_made / times_taken * 100), 2) if times_taken > 0 else 0
            takers.append({
                'user_id': user_id,
                'username': username,
                'times_taken': times_taken,
                'contracts_made': contracts_made,
                'success_rate': success_rate,
                'avg_points_made': round(avg_points, 2) if avg_points else 0
            })
        
        return takers


def get_score_distribution(db):
    """Récupère la distribution des scores par manche"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT 
                CASE 
                    WHEN gp.team = 'A' THEN h.points_made_team_a
                    WHEN gp.team = 'B' THEN h.points_made_team_b
                    ELSE 0
                END as points_made,
                COUNT(*) as count
            FROM hands h
            JOIN game_players gp ON gp.user_id = h.taker_user_id AND gp.game_id = h.game_id
            WHERE h.taker_user_id IS NOT NULL
            GROUP BY points_made
            ORDER BY points_made
        """)
        
        points_distribution = {}
        for row in cur.fetchall():
            points, count = row
            bucket = (points // 10) * 10
            points_distribution[bucket] = points_distribution.get(bucket, 0) + count
        
        return points_distribution


def get_team_performance(db):
    """Analyse la performance des paires de joueurs"""
    with closing(db.cursor()) as cur:
        cur.execute("""
            SELECT 
                u1.username || ' & ' || u2.username as pair_name,
                COUNT(DISTINCT g.id) as games_played,
                SUM(CASE 
                    WHEN g.state = 'terminee' AND gp1.team = 'A' AND g.points_team_a > g.points_team_b THEN 1
                    WHEN g.state = 'terminee' AND gp1.team = 'B' AND g.points_team_b > g.points_team_a THEN 1
                    ELSE 0
                END) as games_won,
                AVG(CASE 
                    WHEN gp1.team = 'A' THEN g.points_team_a
                    WHEN gp1.team = 'B' THEN g.points_team_b
                    ELSE 0
                END) as avg_points
            FROM game_players gp1
            JOIN game_players gp2 ON gp2.game_id = gp1.game_id 
                AND gp2.team = gp1.team 
                AND gp2.user_id > gp1.user_id
            JOIN users u1 ON u1.id = gp1.user_id
            JOIN users u2 ON u2.id = gp2.user_id
            JOIN games g ON g.id = gp1.game_id
            WHERE g.state = 'terminee'
            GROUP BY gp1.user_id, gp2.user_id, u1.username, u2.username
            HAVING games_played > 0
            ORDER BY games_won DESC, games_played DESC
            LIMIT 10
        """)
        
        pairs = []
        for row in cur.fetchall():
            pair_name, games_played, games_won, avg_points = row
            win_rate = round((games_won / games_played * 100), 2) if games_played > 0 else 0
            pairs.append({
                'pair_name': pair_name,
                'games_played': games_played,
                'games_won': games_won,
                'win_rate': win_rate,
                'avg_points': round(avg_points, 2) if avg_points else 0
            })
        
        return {
            'pairs': pairs
        }

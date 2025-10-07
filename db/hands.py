from contextlib import closing


def list_hands(db, game_id: int):
    with closing(db.cursor()) as cur:
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
        return cur.fetchall()


def next_hand_number(db, game_id: int) -> int:
    with closing(db.cursor()) as cur:
        cur.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM hands WHERE game_id = ?", (game_id,))
        return cur.fetchone()[0]


def insert_hand(db, game_id: int, number: int, taker_user_id, contract, trump,
                score_a: int, score_b: int, pre_a: int, pre_b: int,
                coinche: int, surcoinche: int, capot_team, belote_a: int, belote_b: int, general: int, now: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            """
            INSERT INTO hands (game_id, number, taker_user_id, contract, trump,
              score_team_a, score_team_b, points_made_team_a, points_made_team_b,
              coinche, surcoinche, capot_team, belote_a, belote_b, general, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, number, taker_user_id, contract, trump,
             score_a, score_b, pre_a, pre_b,
             coinche, surcoinche, capot_team, belote_a, belote_b, general, now),
        )
        db.commit()


def get_hand(db, hand_id: int):
    with closing(db.cursor()) as cur:
        cur.execute(
            """
            SELECT h.id, h.game_id, h.number, h.taker_user_id, h.contract, h.trump,
                   h.score_team_a, h.score_team_b, h.points_made_team_a, h.points_made_team_b,
                   h.coinche, h.surcoinche, h.capot_team, h.belote_a, h.belote_b, h.general, h.created_at
            FROM hands h
            WHERE h.id = ?
            """,
            (hand_id,),
        )
        return cur.fetchone()


def update_hand(db, hand_id: int, taker_user_id, contract, trump,
                score_a: int, score_b: int, pre_a: int, pre_b: int,
                coinche: int, surcoinche: int, capot_team, belote_a: int, belote_b: int, general: int):
    with closing(db.cursor()) as cur:
        cur.execute(
            """
            UPDATE hands
            SET taker_user_id = ?, contract = ?, trump = ?,
                score_team_a = ?, score_team_b = ?,
                points_made_team_a = ?, points_made_team_b = ?,
                coinche = ?, surcoinche = ?, capot_team = ?,
                belote_a = ?, belote_b = ?, general = ?
            WHERE id = ?
            """,
            (taker_user_id, contract, trump,
             score_a, score_b,
             pre_a, pre_b,
             coinche, surcoinche, capot_team,
             belote_a, belote_b, general,
             hand_id),
        )
        db.commit()


def delete_hand(db, hand_id: int):
    with closing(db.cursor()) as cur:
        cur.execute("DELETE FROM hands WHERE id = ?", (hand_id,))
        db.commit()

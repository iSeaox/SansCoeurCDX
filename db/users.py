from contextlib import closing


def get_active_users(db):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id, username FROM users WHERE is_active = 1 ORDER BY username")
        return cur.fetchall()


def find_user_by_username(db, username: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, username, password_hash, is_active FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
            (username,),
        )
        return cur.fetchone()


def create_user(db, username: str, password_hash: str, created_at: str):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active) VALUES (?, ?, ?, 1)",
            (username, password_hash, created_at),
        )
        db.commit()
        return cur.lastrowid

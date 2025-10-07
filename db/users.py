from contextlib import closing


def get_active_users(db):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id, username FROM users WHERE is_active = 1 ORDER BY username")
        return cur.fetchall()


def find_user_by_username(db, username: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, username, password_hash, is_active, is_admin FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
            (username,),
        )
        return cur.fetchone()


def create_user(db, username: str, password_hash: str, created_at: str):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin) VALUES (?, ?, ?, 1, 0)",
            (username, password_hash, created_at),
        )
        db.commit()
        return cur.lastrowid


def create_user_with_admin(db, username: str, password_hash: str, created_at: str, is_admin: bool = False):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin) VALUES (?, ?, ?, 1, ?)",
            (username, password_hash, created_at, 1 if is_admin else 0),
        )
        db.commit()
        return cur.lastrowid


def create_user_with_admin(db, username: str, password_hash: str, created_at: str, is_admin: bool = False):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin) VALUES (?, ?, ?, 1, ?)",
            (username, password_hash, created_at, 1 if is_admin else 0),
        )
        db.commit()
        return cur.lastrowid


def list_all_users(db):
    """Return all users with id, username, is_active, is_admin, created_at"""
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id, username, is_active, is_admin, created_at FROM users ORDER BY username")
        return cur.fetchall()


def toggle_user_status(db, user_id: int):
    """Toggle is_active status for a user"""
    with closing(db.cursor()) as cur:
        cur.execute("UPDATE users SET is_active = 1 - is_active WHERE id = ?", (user_id,))
        db.commit()
        return cur.rowcount > 0

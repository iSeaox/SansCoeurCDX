from contextlib import closing
from typing import Optional
from datetime import datetime


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


def find_user_by_email(db, email: str):
    if not email:
        return None
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, username, password_hash, is_active, is_admin, email FROM users WHERE email = ? COLLATE NOCASE LIMIT 1",
            (email,),
        )
        return cur.fetchone()


def find_user_by_id(db, user_id: int):
    """Return a tuple: (id, username, email, is_active, is_admin) for the given user_id, or None."""
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, username, email, is_active, is_admin FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        )
        return cur.fetchone()


def set_password_reset_token(db, user_id: int, token: str, expires_at_iso: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "UPDATE users SET reset_token = ?, reset_token_expires_at = ?, last_password_reset_request_at = ? WHERE id = ?",
            (token, expires_at_iso, datetime.utcnow().isoformat(timespec='seconds'), user_id),
        )
        db.commit()
        return cur.rowcount > 0


def get_user_by_reset_token(db, token: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id, username, email, reset_token_expires_at FROM users WHERE reset_token = ? LIMIT 1",
            (token,),
        )
        return cur.fetchone()


def clear_reset_token(db, user_id: int):
    with closing(db.cursor()) as cur:
        cur.execute(
            "UPDATE users SET reset_token = NULL, reset_token_expires_at = NULL WHERE id = ?",
            (user_id,),
        )
        db.commit()
        return cur.rowcount > 0


def update_user_password_hash(db, user_id: int, password_hash: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def can_request_password_reset(db, user_id: int, min_days: int = 30) -> bool:
    """Return True if last_password_reset_request_at older than min_days or NULL."""
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT last_password_reset_request_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return True
        try:
            last = datetime.fromisoformat(row[0])
        except Exception:
            return True
        delta = datetime.utcnow() - last
        return delta.days >= min_days


def update_user_username(db, user_id: int, new_username: str):
    with closing(db.cursor()) as cur:
        cur.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def email_in_use_by_other(db, email: str, exclude_user_id: int) -> bool:
    if not email:
        return False
    with closing(db.cursor()) as cur:
        cur.execute(
            "SELECT id FROM users WHERE email = ? COLLATE NOCASE AND id != ? LIMIT 1",
            (email, exclude_user_id),
        )
        return cur.fetchone() is not None


def update_user_email(db, user_id: int, email: Optional[str]):
    with closing(db.cursor()) as cur:
        cur.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            (email, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def create_user(db, username: str, password_hash: str, created_at: str, email: Optional[str] = None):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        if email:
            cur.execute(
                "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
                (email,),
            )
            if cur.fetchone():
                return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin, email) VALUES (?, ?, ?, 1, 0, ?)",
            (username, password_hash, created_at, email),
        )
        db.commit()
        return cur.lastrowid


def create_user_with_admin(db, username: str, password_hash: str, created_at: str, is_admin: bool = False, email: Optional[str] = None):
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            return None
        if email:
            cur.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,))
            if cur.fetchone():
                return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin, email) VALUES (?, ?, ?, 1, ?, ?)",
            (username, password_hash, created_at, 1 if is_admin else 0, email),
        )
        db.commit()
        return cur.lastrowid


def create_inactive_user(db, username: str, password_hash: str, created_at: str, email: Optional[str] = None):
    """Create an inactive user (for self-registration)"""
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,))
        if cur.fetchone():
            print("User already used")
            return None
        if email:
            cur.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,))
            if cur.fetchone():
                print("Email already used")
                return None
        cur.execute(
            "INSERT INTO users (username, password_hash, created_at, is_active, is_admin, email) VALUES (?, ?, ?, 0, 0, ?)",
            (username, password_hash, created_at, email),
        )
        db.commit()
        return cur.lastrowid


def list_all_users(db):
    """Return all users with id, username, is_active, is_admin, created_at"""
    with closing(db.cursor()) as cur:
        cur.execute("SELECT id, username, is_active, is_admin, created_at, email FROM users ORDER BY username")
        return cur.fetchall()


def toggle_user_status(db, user_id: int):
    """Toggle is_active status for a user"""
    with closing(db.cursor()) as cur:
        cur.execute("UPDATE users SET is_active = 1 - is_active WHERE id = ?", (user_id,))
        db.commit()
        return cur.rowcount > 0


def can_delete_user(db, user_id: int) -> bool:
    """Return True if the user has no references in games, game_players, or hands."""
    with closing(db.cursor()) as cur:

        cur.execute("SELECT COUNT(1) FROM games WHERE created_by = ?", (user_id,))
        cnt_games = cur.fetchone()[0]
        if cnt_games and cnt_games > 0:
            return False

        cur.execute("SELECT COUNT(1) FROM game_players WHERE user_id = ?", (user_id,))
        cnt_gp = cur.fetchone()[0]
        if cnt_gp and cnt_gp > 0:
            return False

        cur.execute("SELECT COUNT(1) FROM hands WHERE taker_user_id = ?", (user_id,))
        cnt_hands = cur.fetchone()[0]
        if cnt_hands and cnt_hands > 0:
            return False
    return True


def delete_user_if_no_references(db, user_id: int) -> bool:
    """Delete user only if they are not referenced anywhere. Returns True on success."""
    if not can_delete_user(db, user_id):
        return False
    with closing(db.cursor()) as cur:
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        return cur.rowcount > 0

import os
import sqlite3
from contextlib import closing
from flask import g


def get_db(app):
    db = getattr(g, '_database', None)
    if db is None:
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
            from .schema import init_db
            init_db(app, db)
    return db


def close_db(exception=None):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


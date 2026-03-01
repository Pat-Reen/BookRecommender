import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "books.db"


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                author     TEXT NOT NULL,
                year       INTEGER,
                rating     INTEGER,
                format     TEXT,
                status     TEXT,
                notes      TEXT,
                date_added TEXT DEFAULT (datetime('now'))
            )
        """)


def add_book(title, author, year=None, rating=None, format=None, status="read", notes=None):
    with _connect() as con:
        con.execute(
            """
            INSERT INTO books (title, author, year, rating, format, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, author, year, rating, format, status, notes),
        )


def get_books():
    with _connect() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM books ORDER BY date_added DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_book(book_id):
    with _connect() as con:
        con.execute("DELETE FROM books WHERE id = ?", (book_id,))

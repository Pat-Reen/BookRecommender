import os
import psycopg2
from psycopg2.extras import RealDictCursor


def _connect():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def init_db():
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id         SERIAL PRIMARY KEY,
                    title      TEXT NOT NULL,
                    author     TEXT NOT NULL,
                    year       INTEGER,
                    rating     INTEGER,
                    format     TEXT,
                    status     TEXT,
                    notes      TEXT,
                    date_added TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reading_list (
                    id         SERIAL PRIMARY KEY,
                    title      TEXT NOT NULL,
                    author     TEXT NOT NULL,
                    year       INTEGER,
                    notes      TEXT,
                    date_added TIMESTAMP DEFAULT NOW()
                )
            """)
        con.commit()
    finally:
        con.close()


def add_to_reading_list(title, author, year=None, notes=None):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO reading_list (title, author, year, notes) VALUES (%s, %s, %s, %s)",
                (title, author, year, notes),
            )
        con.commit()
    finally:
        con.close()


def get_reading_list():
    con = _connect()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM reading_list ORDER BY date_added DESC")
            rows = cur.fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def update_reading_list_item(item_id, title, author, year=None, notes=None):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(
                "UPDATE reading_list SET title=%s, author=%s, year=%s, notes=%s WHERE id=%s",
                (title, author, year, notes, item_id),
            )
        con.commit()
    finally:
        con.close()


def delete_from_reading_list(item_id):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM reading_list WHERE id = %s", (item_id,))
        con.commit()
    finally:
        con.close()


def add_book(title, author, year=None, rating=None, format=None, status="read", notes=None):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (title, author, year, rating, format, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (title, author, year, rating, format, status, notes),
            )
        con.commit()
    finally:
        con.close()


def get_books():
    con = _connect()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM books ORDER BY date_added DESC")
            rows = cur.fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def update_book(book_id, title, author, year=None, rating=None, format=None, status="read", notes=None):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE books SET title=%s, author=%s, year=%s, rating=%s, format=%s, status=%s, notes=%s
                WHERE id=%s
                """,
                (title, author, year, rating, format, status, notes, book_id),
            )
        con.commit()
    finally:
        con.close()


def delete_book(book_id):
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
        con.commit()
    finally:
        con.close()

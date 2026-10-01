import sqlite3

def conn():
    c = sqlite3.connect("app.db")
    c.row_factory = sqlite3.Row
    return c

def init():
    c = conn()
    c.executescript("""
    DROP TABLE IF EXISTS students; DROP TABLE IF EXISTS documents;
    DROP TABLE IF EXISTS queries;  DROP TABLE IF EXISTS notifications;
    CREATE TABLE students(student_id TEXT PRIMARY KEY, name TEXT, branch TEXT,
        year TEXT, language TEXT, scholarship TEXT);
    CREATE TABLE documents(id INTEGER PRIMARY KEY, student_id TEXT, doc_type TEXT,
        file_name TEXT, status TEXT, reason TEXT);
    CREATE TABLE queries(id INTEGER PRIMARY KEY, student_id TEXT, category TEXT,
        text TEXT, resolved INTEGER, office TEXT, ts DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE notifications(id INTEGER PRIMARY KEY, student_id TEXT,
        priority TEXT, message TEXT, ts DEFAULT CURRENT_TIMESTAMP);
    """)
    c.commit()

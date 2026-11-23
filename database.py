import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# absolute path so the database is always created next to this file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn

def init_db():
    # creates tables on first run; does nothing if they already exist
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT,
            action TEXT,
            status TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Seed default system administrator (username: admin / password: admin123) if none exists
    admin_exists = conn.execute("SELECT id FROM admins WHERE username = 'admin'").fetchone()
    if not admin_exists:
        conn.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()

def create_admin(username, password):
    # creates or updates an administrator account
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO admins (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password))
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def create_user(username, password, make_admin=False):
    conn = get_connection()
    try:
        # we store only a salted hash, never the real password
        pw_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, pw_hash)
        )
        if make_admin:
            conn.execute(
                "INSERT OR REPLACE INTO admins (username, password_hash) VALUES (?, ?)",
                (username, pw_hash)
            )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # username column is UNIQUE, so a duplicate fails here
    finally:
        conn.close()

def promote_user_to_admin(user_id):
    # grants administrator privileges to an existing user
    conn = get_connection()
    try:
        user = conn.execute("SELECT username, password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False
        conn.execute(
            "INSERT OR REPLACE INTO admins (username, password_hash) VALUES (?, ?)",
            (user["username"], user["password_hash"])
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def is_user_admin(username):
    conn = get_connection()
    admin = conn.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone()
    conn.close()
    return admin is not None

def verify_user(username, password):
    # returns the user's id if the login is correct, otherwise None
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        return user["id"]
    return None

def verify_admin(username, password):
    # verifies administrator credentials
    conn = get_connection()
    admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
    conn.close()
    if admin and check_password_hash(admin["password_hash"], password):
        return admin["id"]
    return None

def log_activity(user_id, filename, action, status):
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO logs (user_id, filename, action, status, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, filename, action, status, timestamp)
    )
    conn.commit()
    conn.close()

def get_logs(user_id):
    # only this user's rows, newest first (including username and id)
    conn = get_connection()
    rows = conn.execute("""
        SELECT logs.id, users.username, logs.filename, logs.action, logs.status, logs.timestamp
        FROM logs
        JOIN users ON logs.user_id = users.id
        WHERE logs.user_id = ?
        ORDER BY logs.id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows

def clear_logs(user_id):
    # deletes all activity records for the currently authenticated user
    conn = get_connection()
    conn.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def delete_log(log_id, user_id):
    # deletes a specific log entry ensuring it belongs to the logged-in user
    conn = get_connection()
    conn.execute("DELETE FROM logs WHERE id = ? AND user_id = ?", (log_id, user_id))
    conn.commit()
    conn.close()

# --- Administrator Query & Management Functions ---

def get_all_users():
    # returns all registered users with their total logged operation count and admin status
    conn = get_connection()
    rows = conn.execute("""
        SELECT 
            users.id, 
            users.username, 
            COUNT(logs.id) as log_count,
            CASE WHEN admins.id IS NOT NULL THEN 1 ELSE 0 END as is_admin
        FROM users
        LEFT JOIN logs ON users.id = logs.user_id
        LEFT JOIN admins ON users.username = admins.username
        GROUP BY users.id
        ORDER BY users.id ASC
    """).fetchall()
    conn.close()
    return rows

def get_all_logs():
    # returns all user logs across the entire system
    conn = get_connection()
    rows = conn.execute("""
        SELECT logs.id, users.username, logs.filename, logs.action, logs.status, logs.timestamp
        FROM logs
        JOIN users ON logs.user_id = users.id
        ORDER BY logs.id DESC
    """).fetchall()
    conn.close()
    return rows

def delete_user(user_id):
    # deletes a user and all their associated activity logs
    conn = get_connection()
    conn.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def admin_delete_log(log_id):
    # administrator delete for any log entry
    conn = get_connection()
    conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))
    conn.commit()
    conn.close()

def admin_clear_all_logs():
    # administrator wipe for all system logs
    conn = get_connection()
    conn.execute("DELETE FROM logs")
    conn.commit()
    conn.close()

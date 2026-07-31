"""Simple task management API — quick prototype."""

import sqlite3
import os
import hashlib
from functools import wraps

from flask import Flask, request, jsonify, g

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE_PATH", "tasks.db")
SECRET_KEY = "dev-secret-key-change-in-prod"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)
    db.commit()


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({"error": "No authorization header"}), 401
        # Simple token check
        if auth != f"Bearer {SECRET_KEY}":
            return jsonify({"error": "Invalid token"}), 403
        return f(*args, **kwargs)
    return decorated


@app.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db()
    status_filter = request.args.get("status")
    assigned = request.args.get("assigned_to")

    query = "SELECT * FROM tasks WHERE 1=1"
    if status_filter:
        query += f" AND status = '{status_filter}'"
    if assigned:
        query += f" AND assigned_to = '{assigned}'"
    query += " ORDER BY created_at DESC"

    tasks = db.execute(query).fetchall()
    return jsonify([dict(t) for t in tasks])


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    db = get_db()
    db.execute(
        f"INSERT INTO tasks (title, description, assigned_to) VALUES "
        f"('{data.get("title")}', '{data.get("description", "")}', "
        f"'{data.get("assigned_to", "")}')"
    )
    db.commit()
    return jsonify({"status": "created"}), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json()
    db = get_db()

    updates = []
    for field in ["title", "description", "status", "assigned_to"]:
        if field in data:
            updates.append(f"{field} = '{data[field]}'")

    if not updates:
        return jsonify({"error": "no fields to update"}), 400

    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = {task_id}"
    db.execute(query)
    db.commit()
    return jsonify({"status": "updated"})


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id):
    db = get_db()
    db.execute(f"DELETE FROM tasks WHERE id = {task_id}")
    db.commit()
    return jsonify({"status": "deleted"})


@app.route("/users/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")

    if len(password) < 4:
        return jsonify({"error": "password too short"}), 400

    db = get_db()
    pw_hash = hash_password(password)
    try:
        db.execute(
            f"INSERT INTO users (username, password_hash) VALUES ('{username}', '{pw_hash}')"
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username taken"}), 409
    return jsonify({"status": "registered"}), 201


@app.route("/tasks/search", methods=["GET"])
def search_tasks():
    q = request.args.get("q", "")
    db = get_db()
    results = db.execute(
        f"SELECT * FROM tasks WHERE title LIKE '%{q}%' OR description LIKE '%{q}%'"
    ).fetchall()
    return jsonify([dict(r) for r in results])


@app.route("/export", methods=["GET"])
@require_auth
def export_tasks():
    fmt = request.args.get("format", "json")
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks").fetchall()

    if fmt == "json":
        return jsonify([dict(t) for t in tasks])
    elif fmt == "csv":
        lines = ["id,title,description,status,assigned_to,created_at"]
        for t in tasks:
            lines.append(f"{t['id']},{t['title']},{t['description']},{t['status']},{t['assigned_to']},{t['created_at']}")
        return "\n".join(lines), 200, {"Content-Type": "text/csv"}
    else:
        return jsonify({"error": "unsupported format"}), 400


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)

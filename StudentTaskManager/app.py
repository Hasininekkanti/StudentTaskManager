from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "student-task-manager-secret-key")

DATABASE = "tasks.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            priority TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    admin = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        (admin_username,)
    ).fetchone()

    if not admin:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (
                admin_username,
                generate_password_hash(admin_password),
                "admin"
            )
        )

    conn.commit()
    conn.close()


def login_required():
    return "user_id" in session


def admin_required():
    return session.get("role") == "admin"


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password_hash"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        if not username:
            flash("Username is required.", "error")
            return render_template("register.html")

        conn = get_db()

        try:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    "user"
                )
            )

            conn.commit()
            flash("Registration successful. Please login.", "success")

            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.close()
            flash("Username already exists.", "error")

    return render_template("register.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    conn = get_db()

    tasks = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        tasks=tasks
    )


@app.route("/add", methods=["POST"])
def add_task():

    if not login_required():
        return redirect(url_for("login"))

    title = request.form["title"].strip()
    priority = request.form["priority"]

    if title:

        conn = get_db()

        conn.execute(
            """
            INSERT INTO tasks (user_id, title, priority)
            VALUES (?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                priority
            )
        )

        conn.commit()
        conn.close()

    return redirect(url_for("dashboard"))


@app.route("/complete/<int:task_id>")
def complete_task(task_id):

    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute(
        """
        UPDATE tasks
        SET completed = 1
        WHERE id = ? AND user_id = ?
        """,
        (
            task_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/delete/<int:task_id>")
def delete_task(task_id):

    if not login_required():
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute(
        """
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
        """,
        (
            task_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/admin")
def admin_dashboard():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        flash("Admin access required.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db()

    users = conn.execute(
        """
        SELECT
            users.username,
            users.role,
            COUNT(tasks.id) AS total_tasks,
            SUM(
                CASE
                    WHEN tasks.completed = 1 THEN 1
                    ELSE 0
                END
            ) AS completed_tasks
        FROM users
        LEFT JOIN tasks
            ON users.id = tasks.user_id
        GROUP BY users.id
        ORDER BY users.id
        """
    ).fetchall()

    records = conn.execute(
        """
        SELECT
            users.username,
            tasks.title,
            tasks.priority,
            tasks.completed
        FROM tasks
        JOIN users
            ON tasks.user_id = users.id
        ORDER BY tasks.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        records=records
    )


if __name__ == "__main__":
    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
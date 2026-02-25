from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "meru_poly_enterprise_secret"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

DB = "database.db"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 15000
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        subject TEXT,
        marks INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        message TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        type TEXT,
        description TEXT
    )
    """)

    # Default admin
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username,password,is_admin,balance) VALUES (?,?,?,?)",
                  ("admin", generate_password_hash("admin123"), 1, 0))

    conn.commit()
    conn.close()

# ================= LOGIN =================

class User(UserMixin):
    def __init__(self, id, username, is_admin, balance):
        self.id = id
        self.username = username
        self.is_admin = is_admin
        self.balance = balance

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[3], user[4])
    return None

# ================= ROUTES =================

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO users (username,password,is_admin) VALUES (?,?,0)",
                  (username,password))
        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1], user[3], user[4]))
            if user[3] == 1:
                return redirect("/admin")
            else:
                return redirect("/student")

    return render_template("login.html")

@app.route("/student")
@login_required
def student():
    if current_user.is_admin == 1:
        return redirect("/admin")
    return render_template("student_dashboard.html")

@app.route("/admin")
@login_required
def admin():
    if current_user.is_admin == 0:
        return redirect("/student")
    return render_template("admin_dashboard.html")

# ================= RESULTS =================

def grade(m):
    if m > 80:
        return "Mastery"
    elif m >= 65:
        return "Proficient"
    elif m >= 50:
        return "Competent"
    else:
        return "Not Yet Competent"

@app.route("/results")
@login_required
def results():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT subject,marks FROM results WHERE student_id=?", (current_user.id,))
    data = [(s,m,grade(m)) for s,m in c.fetchall()]
    conn.close()
    return render_template("results.html", results=data)

@app.route("/add_result", methods=["POST"])
@login_required
def add_result():
    if current_user.is_admin == 1:
        sid = request.form["student_id"]
        subject = request.form["subject"]
        marks = request.form["marks"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO results (student_id,subject,marks) VALUES (?,?,?)",
                  (sid,subject,marks))
        conn.commit()
        conn.close()
    return redirect("/admin")

# ================= FEES =================

@app.route("/fees")
@login_required
def fees():
    return render_template("fees.html", balance=current_user.balance)

@app.route("/pay")
@login_required
def pay():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance=0 WHERE id=?", (current_user.id,))
    conn.commit()
    conn.close()
    return redirect("/fees")

@app.route("/download_fee_statement")
@login_required
def download_fee_statement():
    file = "fee_statement.pdf"
    doc = SimpleDocTemplate(file)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Meru Poly Fee Statement", styles["Title"]))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Student: {current_user.username}", styles["Normal"]))
    elements.append(Paragraph(f"Balance: Ksh {current_user.balance}", styles["Normal"]))

    doc.build(elements)
    return send_file(file, as_attachment=True)

# ================= LOGOUT =================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ================= RUN =================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
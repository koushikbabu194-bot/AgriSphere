from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "placement.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','company','admin')),
        phone TEXT,
        department TEXT,
        course TEXT,
        cgpa REAL DEFAULT 0,
        graduation_year INTEGER,
        resume TEXT,
        company_name TEXT,
        location TEXT,
        description TEXT,
        approved INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        salary TEXT,
        min_cgpa REAL DEFAULT 0,
        course TEXT,
        deadline TEXT,
        FOREIGN KEY(company_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Applied',
        UNIQUE(student_id, job_id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        interview_date TEXT NOT NULL,
        interview_time TEXT NOT NULL,
        mode TEXT NOT NULL,
        venue TEXT,
        FOREIGN KEY(application_id) REFERENCES applications(id)
    );
    """)

    admin = conn.execute("SELECT id FROM users WHERE email=?", ("admin@placement.com",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
            ("Administrator", "admin@placement.com",
             generate_password_hash("admin123"), "admin")
        )

    # Demo company accounts and jobs are created only if the jobs table is empty.
    job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    if job_count == 0:
        demo_jobs = [
            ("ABC Technologies", "Python Developer", "Build Python applications and Flask web projects.", "4 LPA", 6.0, "Any"),
            ("Infosys", "Web Developer", "Develop responsive websites using HTML, CSS and JavaScript.", "3.5 LPA", 6.0, "Any"),
            ("TCS", "Java Developer", "Develop and maintain Java-based applications.", "4.5 LPA", 6.5, "Any"),
            ("Wipro", "Data Analyst", "Analyze datasets using Python, Excel and SQL.", "5 LPA", 6.0, "Any"),
            ("Tech Solutions", "Software Engineer", "Design, test and maintain software applications.", "6 LPA", 7.0, "Any")
        ]
        for company, title, description, salary, cgpa, course in demo_jobs:
            email = "demo." + company.lower().replace(" ", "").replace(".", "") + "@example.com"
            row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if row:
                company_id = row["id"]
            else:
                cur = conn.execute("""
                    INSERT INTO users(name,email,password,role,company_name,location,description,approved)
                    VALUES(?,?,?,?,?,?,?,1)
                """, (company, email, generate_password_hash("demo123"), "company",
                      company, "India", "Demo company account"))
                company_id = cur.lastrowid
            conn.execute("""
                INSERT INTO jobs(company_id,title,description,salary,min_cgpa,course)
                VALUES(?,?,?,?,?,?)
            """, (company_id, title, description, salary, cgpa, course))

    conn.commit()
    conn.close()

def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if role and user.get("role") != role:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}

@app.route("/")
def index():
    conn = get_db()
    jobs = conn.execute("""
        SELECT jobs.*, users.company_name, users.name AS company_user
        FROM jobs JOIN users ON jobs.company_id=users.id
        ORDER BY jobs.id DESC LIMIT 6
    """).fetchall()
    conn.close()
    return render_template("index.html", jobs=jobs)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if role not in ("student", "company") or not name or not email or len(password) < 6:
            flash("Enter valid details. Password must contain at least 6 characters.", "danger")
            return render_template("register.html")
        try:
            conn = get_db()
            if role == "student":
                cgpa = float(request.form.get("cgpa") or 0)
                year = int(request.form.get("graduation_year") or 0)
                if not 0 <= cgpa <= 10:
                    raise ValueError
                conn.execute("""
                    INSERT INTO users(name,email,password,role,phone,department,course,cgpa,graduation_year)
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (name,email,generate_password_hash(password),role,
                      request.form.get("phone"),request.form.get("department"),
                      request.form.get("course"),cgpa,year))
            else:
                conn.execute("""
                    INSERT INTO users(name,email,password,role,phone,company_name,location,description,approved)
                    VALUES(?,?,?,?,?,?,?,?,0)
                """, (name,email,generate_password_hash(password),role,
                      request.form.get("phone"),request.form.get("company_name"),
                      request.form.get("location"),request.form.get("description")))
            conn.commit()
            conn.close()
            flash("Registration successful. Company accounts require admin approval.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "danger")
        except ValueError:
            flash("Enter a valid CGPA (0–10) and graduation year.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            if user["role"] == "company" and not user["approved"]:
                flash("Your company account is waiting for admin approval.", "warning")
                return redirect(url_for("login"))
            session.clear()
            session["user"] = dict(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required()
def dashboard():
    role = session["user"]["role"]
    return redirect(url_for({"student":"student_dashboard","company":"company_dashboard","admin":"admin_dashboard"}[role]))

@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    uid = session["user"]["id"]
    conn = get_db()
    jobs = conn.execute("""
        SELECT jobs.*, users.company_name
        FROM jobs JOIN users ON jobs.company_id=users.id
        ORDER BY jobs.id DESC
    """).fetchall()
    apps = conn.execute("""
        SELECT applications.*, jobs.title, users.company_name
        FROM applications JOIN jobs ON applications.job_id=jobs.id
        JOIN users ON jobs.company_id=users.id
        WHERE applications.student_id=? ORDER BY applications.id DESC
    """, (uid,)).fetchall()
    interviews = conn.execute("""
        SELECT interviews.*, jobs.title, users.company_name
        FROM interviews JOIN applications ON interviews.application_id=applications.id
        JOIN jobs ON applications.job_id=jobs.id
        JOIN users ON jobs.company_id=users.id
        WHERE applications.student_id=? ORDER BY interviews.interview_date
    """, (uid,)).fetchall()
    conn.close()
    return render_template("student_dashboard.html", jobs=jobs, apps=apps, interviews=interviews)

@app.route("/student/profile", methods=["GET", "POST"])
@login_required("student")
def student_profile():
    uid = session["user"]["id"]
    conn = get_db()
    if request.method == "POST":
        resume_name = session["user"].get("resume")
        uploaded = request.files.get("resume")
        if uploaded and uploaded.filename:
            safe_name = secure_filename(uploaded.filename)
            ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
            if ext not in ALLOWED_EXTENSIONS:
                conn.close()
                flash("Resume must be PDF, DOC or DOCX.", "danger")
                return redirect(url_for("student_profile"))
            resume_name = f"{uid}_{safe_name}"
            uploaded.save(os.path.join(UPLOAD_DIR, resume_name))
        try:
            cgpa = float(request.form.get("cgpa") or 0)
            year = int(request.form.get("graduation_year") or 0)
            if not 0 <= cgpa <= 10:
                raise ValueError
        except ValueError:
            conn.close()
            flash("Enter a valid CGPA between 0 and 10 and a valid graduation year.", "danger")
            return redirect(url_for("student_profile"))
        conn.execute("""
            UPDATE users SET name=?,phone=?,department=?,course=?,cgpa=?,graduation_year=?,resume=?
            WHERE id=?
        """, (request.form.get("name"),request.form.get("phone"),
              request.form.get("department"),request.form.get("course"),
              cgpa,year,resume_name,uid))
        conn.commit()
        updated = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        session["user"] = dict(updated)
        flash("Profile updated successfully.", "success")
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return render_template("student_profile.html", user=user)

@app.route("/apply/<int:job_id>", methods=["POST"])
@login_required("student")
def apply(job_id):
    uid = session["user"]["id"]
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    student = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not job:
        flash("Job not found.", "danger")
    elif float(student["cgpa"] or 0) < float(job["min_cgpa"] or 0):
        flash("You do not meet the minimum CGPA for this job.", "danger")
    elif job["course"] and job["course"].lower() not in ("any", (student["course"] or "").lower()):
        flash("This job is not listed for your course.", "danger")
    else:
        try:
            conn.execute("INSERT INTO applications(student_id,job_id) VALUES(?,?)", (uid,job_id))
            conn.commit()
            flash("Your application was submitted.", "success")
        except sqlite3.IntegrityError:
            flash("You have already applied for this job.", "warning")
    conn.close()
    return redirect(url_for("student_dashboard"))

@app.route("/company/dashboard")
@login_required("company")
def company_dashboard():
    uid = session["user"]["id"]
    conn = get_db()
    jobs = conn.execute("SELECT * FROM jobs WHERE company_id=? ORDER BY id DESC", (uid,)).fetchall()
    apps = conn.execute("""
        SELECT applications.*, jobs.title, users.name, users.email, users.cgpa, users.resume
        FROM applications JOIN jobs ON applications.job_id=jobs.id
        JOIN users ON applications.student_id=users.id
        WHERE jobs.company_id=? ORDER BY applications.id DESC
    """, (uid,)).fetchall()
    conn.close()
    return render_template("company_dashboard.html", jobs=jobs, apps=apps)

@app.route("/company/job/new", methods=["GET", "POST"])
@login_required("company")
def new_job():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Job title is required.", "danger")
            return redirect(url_for("new_job"))
        try:
            cgpa = float(request.form.get("min_cgpa") or 0)
            if not 0 <= cgpa <= 10:
                raise ValueError
        except ValueError:
            flash("Minimum CGPA must be between 0 and 10.", "danger")
            return redirect(url_for("new_job"))
        conn = get_db()
        conn.execute("""
            INSERT INTO jobs(company_id,title,description,salary,min_cgpa,course,deadline)
            VALUES(?,?,?,?,?,?,?)
        """, (session["user"]["id"],title,request.form.get("description"),
              request.form.get("salary"),cgpa,request.form.get("course"),request.form.get("deadline")))
        conn.commit()
        conn.close()
        flash("Job posted successfully.", "success")
        return redirect(url_for("company_dashboard"))
    return render_template("job_form.html")

@app.route("/company/application/<int:app_id>/status", methods=["POST"])
@login_required("company")
def update_application(app_id):
    status = request.form.get("status")
    allowed = ("Applied", "Shortlisted", "Interview", "Selected", "Rejected")
    if status not in allowed:
        flash("Invalid application status.", "danger")
        return redirect(url_for("company_dashboard"))
    conn = get_db()
    conn.execute("""
        UPDATE applications SET status=?
        WHERE id=? AND job_id IN (SELECT id FROM jobs WHERE company_id=?)
    """, (status,app_id,session["user"]["id"]))
    conn.commit()
    conn.close()
    flash("Application status updated.", "success")
    return redirect(url_for("company_dashboard"))

@app.route("/company/interview/<int:app_id>", methods=["POST"])
@login_required("company")
def schedule_interview(app_id):
    conn = get_db()
    valid = conn.execute("""
        SELECT applications.id FROM applications JOIN jobs ON applications.job_id=jobs.id
        WHERE applications.id=? AND jobs.company_id=?
    """, (app_id,session["user"]["id"])).fetchone()
    date = request.form.get("date")
    time = request.form.get("time")
    mode = request.form.get("mode")
    if valid and date and time and mode:
        conn.execute("""
            INSERT INTO interviews(application_id,interview_date,interview_time,mode,venue)
            VALUES(?,?,?,?,?)
        """, (app_id,date,time,mode,request.form.get("venue")))
        conn.execute("UPDATE applications SET status='Interview' WHERE id=?", (app_id,))
        conn.commit()
        flash("Interview scheduled.", "success")
    else:
        flash("Please provide valid interview details.", "danger")
    conn.close()
    return redirect(url_for("company_dashboard"))

@app.route("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    conn = get_db()
    counts = {
        "students": conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "companies": conn.execute("SELECT COUNT(*) FROM users WHERE role='company'").fetchone()[0],
        "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "applications": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
        "placed": conn.execute("SELECT COUNT(*) FROM applications WHERE status='Selected'").fetchone()[0]
    }
    pending = conn.execute("SELECT * FROM users WHERE role='company' AND approved=0").fetchall()
    students = conn.execute("SELECT * FROM users WHERE role='student' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_dashboard.html", counts=counts, pending=pending, students=students)

@app.route("/admin/company/<int:user_id>/approve", methods=["POST"])
@login_required("admin")
def approve_company(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET approved=1 WHERE id=? AND role='company'", (user_id,))
    conn.commit()
    conn.close()
    flash("Company approved.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/company/<int:user_id>/reject", methods=["POST"])
@login_required("admin")
def reject_company(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET approved=-1 WHERE id=? AND role='company'", (user_id,))
    conn.commit()
    conn.close()
    flash("Company account rejected.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/applications")
@login_required("admin")
def admin_applications():
    conn = get_db()
    apps = conn.execute("""
        SELECT applications.*, users.name AS student, users.email,
               jobs.title, companies.company_name
        FROM applications JOIN users ON applications.student_id=users.id
        JOIN jobs ON applications.job_id=jobs.id
        JOIN users AS companies ON jobs.company_id=companies.id
        ORDER BY applications.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_applications.html", apps=apps)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
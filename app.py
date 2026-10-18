import os
import json
import sqlite3
import time
import re
import secrets
import hashlib
import hmac
import logging
from collections import defaultdict
from functools import wraps
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, jsonify, send_file, g, abort, Response
)
import csv
import io
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv

# Load environment configuration (.env)
load_dotenv()

import database
import email_service
import recruitment_updater
from pdf_generator import generate_paper_pdf

app = Flask(__name__)
app.secret_key = os.environ.get("DEFENCE_PATH_SECRET_KEY", "defence_path_secret_key_2026_command")
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB

# Production Session Security
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False
)

# Login Throttling / Rate-Limiting Store (5 failed attempts per 5 minutes)
LOGIN_ATTEMPTS = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300

def is_rate_limited(key):
    now = time.time()
    LOGIN_ATTEMPTS[key] = [t for t in LOGIN_ATTEMPTS[key] if now - t < LOCKOUT_WINDOW_SECONDS]
    return len(LOGIN_ATTEMPTS[key]) >= MAX_FAILED_ATTEMPTS

def record_failed_attempt(key):
    LOGIN_ATTEMPTS[key].append(time.time())

def clear_failed_attempts(key):
    if key in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[key]

# OTP Throttling & Cooldown Store
OTP_REQUEST_TIMESTAMPS = defaultdict(list)
OTP_COOLDOWN_WINDOW = 60 # 60 seconds cooldown between OTP requests
OTP_MAX_REQUESTS_15MIN = 3
OTP_WINDOW_SECONDS = 900 # 15 minutes

def is_otp_rate_limited(key):
    if app.config.get('TESTING'):
        return False, ""
    now = time.time()
    # Enforce request cooldown
    if OTP_REQUEST_TIMESTAMPS[key] and (now - OTP_REQUEST_TIMESTAMPS[key][-1] < OTP_COOLDOWN_WINDOW):
        remaining = int(OTP_COOLDOWN_WINDOW - (now - OTP_REQUEST_TIMESTAMPS[key][-1]))
        return True, f"Please wait {remaining} seconds before requesting another verification code."
    # Enforce window max
    OTP_REQUEST_TIMESTAMPS[key] = [t for t in OTP_REQUEST_TIMESTAMPS[key] if now - t < OTP_WINDOW_SECONDS]
    if len(OTP_REQUEST_TIMESTAMPS[key]) >= OTP_MAX_REQUESTS_15MIN:
        return True, "Too many verification requests. Please wait 15 minutes before attempting again."
    return False, ""

def record_otp_request(key):
    OTP_REQUEST_TIMESTAMPS[key].append(time.time())

def generate_secure_otp():
    """Generates a cryptographically random 6-digit numeric OTP."""
    return ''.join(secrets.choice('0123456789') for _ in range(6))

def hash_token(val):
    """Returns SHA-256 hex digest of a token or OTP."""
    return hashlib.sha256(val.strip().encode('utf-8')).hexdigest()

def get_or_create_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(24)
    return session['csrf_token']

# Initialize database if not exists and apply safe schema migrations
if not os.path.exists(database.DB_PATH):
    database.init_db()
    database.seed_data()
database.migrate_db()

def get_db():
    if 'db' not in g:
        g.db = database.get_db()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Context processor to inject dynamic developer profile, site settings, and live stats everywhere
@app.context_processor
def inject_global_data():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM developer_profile ORDER BY id DESC LIMIT 1")
    dev_row = c.fetchone()
    dev = dict(dev_row) if dev_row else {
        "name": "Er. Prashant Mishra",
        "title": "Project Developer – Defence Path",
        "contact_number": "6390314464",
        "email": None,
        "profile_image": "/static/uploads/developer/prashant_image.jpeg",
        "bio": "Project Developer and Lead System Architect of Defence Path."
    }

    try:
        c.execute("SELECT key, value FROM site_settings")
        settings_dict = {row['key']: row['value'] for row in c.fetchall()}
    except Exception:
        settings_dict = {}

    return dict(
        dev=dev,
        global_settings=settings_dict,
        mock_test_price=settings_dict.get('mock_test_price', '5'),
        broadcast_announcement=settings_dict.get('site_announcement', 'Welcome to DEFENCE PATH - Official Defence Recruitment, PYQs & CBT Mock Test Portal.')
    )

# Authentication Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Authentication required to access this command page.", "warning")
            return redirect(url_for('login_view', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Administrator authentication required.", "warning")
            return redirect(url_for('admin_login', next=request.url))
        if session.get('role') != 'admin':
            flash("Access denied. Insufficient administrative privileges.", "danger")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# PUBLIC & HOME ROUTES
# ==========================================

@app.route('/')
def home():
    db = get_db()
    c = db.cursor()

    # Dynamic Statistics
    c.execute("SELECT COUNT(*) FROM defence_exams WHERE is_active = 1")
    exams_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM recruitments")
    active_jobs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM test_papers WHERE is_published = 1")
    tests_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]

    # Recent Jobs (top 6)
    c.execute("SELECT * FROM recruitments ORDER BY id DESC LIMIT 6")
    recent_jobs = [dict(r) for r in c.fetchall()]

    # Recent Papers / Mocks (top 6)
    c.execute("SELECT * FROM test_papers WHERE is_published = 1 ORDER BY id DESC LIMIT 6")
    recent_papers = [dict(p) for p in c.fetchall()]

    # Active announcements
    c.execute("SELECT * FROM announcements WHERE is_active = 1 ORDER BY id DESC LIMIT 5")
    announcements = [dict(a) for a in c.fetchall()]

    stats = {
        "exams_count": exams_count,
        "active_jobs": active_jobs,
        "tests_count": tests_count,
        "users_count": users_count
    }

    return render_template(
        'index.html',
        stats=stats,
        recent_jobs=recent_jobs,
        recent_papers=recent_papers,
        announcements=announcements
    )

@app.route('/jobs')
def jobs_view():
    db = get_db()
    c = db.cursor()

    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()

    sql = "SELECT * FROM recruitments WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR post_name LIKE ? OR organization LIKE ? OR qualification LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term, term])

    if category:
        sql += " AND category = ?"
        params.append(category)

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"
    c.execute(sql, params)
    jobs = [dict(r) for r in c.fetchall()]

    return render_template(
        'jobs.html',
        jobs=jobs,
        query_q=q,
        query_cat=category,
        query_status=status
    )

@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM recruitments WHERE id = ?", (job_id,))
    job_row = c.fetchone()
    if not job_row:
        flash("Recruitment notice not found.", "warning")
        return redirect(url_for('jobs_view'))
    return render_template('jobs.html', jobs=[dict(job_row)], query_q='', query_cat='', query_status='')

@app.route('/portals')
def portals_view():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM official_portals ORDER BY id ASC")
    portals = [dict(p) for p in c.fetchall()]
    return render_template('portals.html', portals=portals)

@app.route('/eligibility')
def eligibility_view():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM defence_exams WHERE is_active = 1 ORDER BY id ASC")
    exams = [dict(e) for e in c.fetchall()]
    return render_template('eligibility.html', exams=exams)

@app.route('/exams')
@app.route('/exams/<exam_code>')
def exams_view(exam_code=None):
    db = get_db()
    c = db.cursor()
    if exam_code:
        c.execute("SELECT * FROM defence_exams WHERE code = ? COLLATE NOCASE AND is_active = 1", (exam_code,))
    else:
        c.execute("SELECT * FROM defence_exams WHERE is_active = 1 ORDER BY id ASC")
    exams = [dict(e) for e in c.fetchall()]

    if not exams and exam_code:
        flash(f"Examination '{exam_code}' not found.", "warning")
        return redirect(url_for('exams_view'))

    # Load structured syllabus grouped by exam
    c.execute("SELECT * FROM exam_syllabus ORDER BY exam_code ASC, id ASC")
    all_syllabus = [dict(s) for s in c.fetchall()]
    syllabus_by_exam = defaultdict(list)
    for s in all_syllabus:
        syllabus_by_exam[s['exam_code']].append(s)

    return render_template(
        'exams.html',
        exams=exams,
        syllabus_by_exam=syllabus_by_exam,
        selected_code=exam_code
    )

@app.route('/sitemap.xml')
def sitemap_xml():
    db = get_db()
    c = db.cursor()

    base_url = request.url_root.rstrip('/')

    static_urls = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/jobs", "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base_url}/portals", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/eligibility", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/exams", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/pyq", "changefreq": "daily", "priority": "0.8"},
        {"loc": f"{base_url}/tests", "changefreq": "daily", "priority": "0.8"},
        {"loc": f"{base_url}/about", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/developer-profile", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/contact", "changefreq": "monthly", "priority": "0.5"},
    ]

    c.execute("SELECT id FROM recruitments ORDER BY id DESC")
    job_urls = [
        {"loc": f"{base_url}/jobs/{r['id']}", "changefreq": "daily", "priority": "0.8"}
        for r in c.fetchall()
    ]

    c.execute("SELECT code FROM defence_exams WHERE is_active = 1")
    exam_urls = [
        {"loc": f"{base_url}/exams/{e['code']}", "changefreq": "weekly", "priority": "0.7"}
        for e in c.fetchall()
    ]

    c.execute("SELECT id FROM test_papers WHERE is_published = 1")
    paper_urls = [
        {"loc": f"{base_url}/pyq-view/{p['id']}", "changefreq": "weekly", "priority": "0.7"}
        for p in c.fetchall()
    ]

    all_urls = static_urls + job_urls + exam_urls + paper_urls
    today_str = datetime.now().strftime("%Y-%m-%d")

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in all_urls:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{u["loc"]}</loc>')
        xml_lines.append(f'    <lastmod>{today_str}</lastmod>')
        xml_lines.append(f'    <changefreq>{u["changefreq"]}</changefreq>')
        xml_lines.append(f'    <priority>{u["priority"]}</priority>')
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')

    return Response("\n".join(xml_lines), mimetype='application/xml')

@app.route('/robots.txt')
def robots_txt():
    base_url = request.url_root.rstrip('/')
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /jobs",
        "Allow: /jobs/*",
        "Allow: /portals",
        "Allow: /eligibility",
        "Allow: /exams",
        "Allow: /exams/*",
        "Allow: /pyq",
        "Allow: /pyq-view/*",
        "Allow: /tests",
        "Allow: /about",
        "Allow: /developer-profile",
        "Allow: /contact",
        "Disallow: /admin",
        "Disallow: /admin/*",
        "Disallow: /dashboard",
        "Disallow: /profile",
        "Disallow: /my-applications",
        "Disallow: /saved-jobs",
        "Disallow: /study-planner",
        "Disallow: /weakness-analysis",
        "Disallow: /test-cbt/*",
        "Disallow: /start-test/*",
        "Disallow: /test-payment/*",
        "Disallow: /api/*",
        "Disallow: /forgot-password",
        f"Sitemap: {base_url}/sitemap.xml"
    ]
    return Response("\n".join(lines), mimetype='text/plain')

@app.route('/pyq')
def pyq_library():
    db = get_db()
    c = db.cursor()

    exam = request.args.get('exam', '').strip()
    subject = request.args.get('subject', '').strip()
    difficulty = request.args.get('difficulty', '').strip()

    sql = "SELECT * FROM test_papers WHERE paper_type = 'PYQ' AND is_published = 1"
    params = []

    if exam:
        sql += " AND exam_code = ?"
        params.append(exam)
    if subject:
        sql += " AND subject = ?"
        params.append(subject)
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)

    sql += " ORDER BY year DESC, id DESC"
    c.execute(sql, params)
    papers = [dict(p) for p in c.fetchall()]

    return render_template(
        'pyqs.html',
        papers=papers,
        query_exam=exam,
        query_sub=subject,
        query_diff=difficulty
    )

@app.route('/pyq-view/<int:paper_id>')
def pyq_view(paper_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Question paper not found.", "warning")
        return redirect(url_for('pyq_library'))

    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (paper_id,))
    questions = [dict(q) for q in c.fetchall()]

    return render_template('pyq_view.html', paper=dict(p_row), questions=questions)

@app.route('/tests')
def tests_view():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers WHERE is_published = 1 ORDER BY id ASC")
    mock_tests = [dict(t) for t in c.fetchall()]

    user_id = session.get('user_id')
    free_attempt_available = False
    unlocked_paper_ids = []
    pending_paper_ids = []

    if user_id:
        c.execute("SELECT free_attempt_used, role FROM users WHERE id = ?", (user_id,))
        u_row = c.fetchone()
        if u_row:
            if u_row['role'] == 'admin':
                free_attempt_available = True
                unlocked_paper_ids = [t['id'] for t in mock_tests]
            else:
                free_attempt_available = (u_row['free_attempt_used'] == 0)

            c.execute("SELECT paper_id FROM test_entitlements WHERE user_id = ? AND is_consumed = 0", (user_id,))
            unlocked_paper_ids.extend([row[0] for row in c.fetchall()])

            c.execute("SELECT paper_id FROM payment_transactions WHERE user_id = ? AND status = 'Pending'", (user_id,))
            pending_paper_ids = [row[0] for row in c.fetchall()]

    mock_test_price = database.get_setting("mock_test_price", "5")

    return render_template(
        'tests.html',
        mock_tests=mock_tests,
        free_attempt_available=free_attempt_available,
        unlocked_paper_ids=set(unlocked_paper_ids),
        pending_paper_ids=set(pending_paper_ids),
        mock_test_price=mock_test_price
    )


# ==========================================
# CBT ENGINE & TEST SUBMISSION API
# ==========================================

@app.route('/test-payment/<int:paper_id>')
@login_required
def test_payment_view(paper_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Examination paper not found.", "warning")
        return redirect(url_for('tests_view'))

    paper = dict(p_row)
    user_id = session.get('user_id')

    # Check for existing pending payment
    c.execute("SELECT * FROM payment_transactions WHERE user_id = ? AND paper_id = ? AND status = 'Pending' ORDER BY id DESC LIMIT 1", (user_id, paper_id))
    pending_row = c.fetchone()
    existing_pending = dict(pending_row) if pending_row else None

    price = database.get_setting("mock_test_price", "5")
    upi_id = database.get_setting("upi_id", "pm204664-1@okaxis")
    upi_name = database.get_setting("upi_name", "Er. Prashant Mishra")
    qr_image = database.get_setting("upi_qr_image", "/static/uploads/payment/prashant_upi_qr.jpeg")

    return render_template(
        'test_payment.html',
        paper=paper,
        price=price,
        upi_id=upi_id,
        upi_name=upi_name,
        qr_image=qr_image,
        existing_pending=existing_pending
    )

@app.route('/api/payment/submit', methods=['POST'])
@login_required
def submit_payment_api():
    paper_id = request.form.get('paper_id')
    transaction_ref = request.form.get('transaction_ref', '').strip()
    user_id = session.get('user_id')

    if not paper_id or not transaction_ref:
        flash("Transaction reference / UTR number is mandatory.", "error")
        return redirect(url_for('test_payment_view', paper_id=paper_id or 1))

    if len(transaction_ref) < 6:
        flash("Please enter a valid 12-digit UPI reference / UTR number.", "error")
        return redirect(url_for('test_payment_view', paper_id=paper_id))

    db = get_db()
    c = db.cursor()

    # Prevent duplicate transaction references
    c.execute("SELECT id, status FROM payment_transactions WHERE transaction_ref = ?", (transaction_ref,))
    existing = c.fetchone()
    if existing:
        flash("This transaction reference has already been submitted.", "warning")
        return redirect(url_for('test_payment_view', paper_id=paper_id))

    proof_path = None
    proof_file = request.files.get('proof_image')
    if proof_file and proof_file.filename:
        filename = secure_filename(f"proof_{user_id}_{int(time.time())}_{proof_file.filename}")
        save_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'payment_proofs')
        os.makedirs(save_dir, exist_ok=True)
        dest_path = os.path.join(save_dir, filename)
        proof_file.save(dest_path)
        proof_path = f"/static/uploads/payment_proofs/{filename}"

    price = float(database.get_setting("mock_test_price", "5.0"))

    c.execute('''
    INSERT INTO payment_transactions (user_id, paper_id, amount, transaction_ref, proof_image, status)
    VALUES (?, ?, ?, ?, ?, 'Pending')
    ''', (user_id, paper_id, price, transaction_ref, proof_path))
    db.commit()

    flash(f"Payment reference '{transaction_ref}' submitted successfully! Awaiting administrator verification.", "success")
    return redirect(url_for('tests_view'))

@app.route('/start-test/<int:paper_id>')
@app.route('/test-cbt/<int:paper_id>')
def start_test(paper_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()

    # Enforce login unless in automated test mode
    if not user_id:
        if not app.config.get('TESTING'):
            flash("Please sign in or register to take this mock test with your free or purchased attempt.", "warning")
            return redirect(url_for('login_view', next=url_for('start_test', paper_id=paper_id)))
        else:
            c.execute("SELECT id FROM users WHERE username = 'aspirant'")
            u_row = c.fetchone()
            user_id = u_row[0] if u_row else 1

    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Examination paper not found.", "warning")
        return redirect(url_for('tests_view'))

    paper = dict(p_row)

    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    if user:
        is_admin = (user['role'] == 'admin')
        has_free_attempt = (user['free_attempt_used'] == 0)

        c.execute("SELECT id FROM test_entitlements WHERE user_id = ? AND paper_id = ? AND is_consumed = 0", (user_id, paper_id))
        entitlement = c.fetchone()

        if not is_admin and not has_free_attempt and not entitlement and not app.config.get('TESTING'):
            c.execute("SELECT id FROM payment_transactions WHERE user_id = ? AND paper_id = ? AND status = 'Pending'", (user_id, paper_id))
            if c.fetchone():
                flash("Your payment for this mock test is pending verification. It will unlock immediately upon verification.", "info")
            else:
                flash("Your 1 free mock test attempt has been consumed. Please unlock this test for ₹5 via UPI QR.", "info")
            return redirect(url_for('test_payment_view', paper_id=paper_id))

    # Fetch associated questions
    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (paper_id,))
    q_rows = c.fetchall()

    if not q_rows:
        c.execute("SELECT * FROM questions WHERE exam_code = ? ORDER BY id ASC", (paper['exam_code'],))
        q_rows = c.fetchall()

    questions = [dict(q) for q in q_rows]

    # SECURITY FIX: Strip correct answers and explanations before sending to client browser
    safe_questions = []
    for q in questions:
        q_copy = dict(q)
        q_copy.pop('correct_option', None)
        q_copy.pop('explanation_en', None)
        q_copy.pop('explanation_hi', None)
        safe_questions.append(q_copy)

    return render_template(
        'test_cbt.html',
        paper=paper,
        paper_json=json.dumps(paper),
        questions_json=json.dumps(safe_questions)
    )

@app.route('/api/submit-test', methods=['POST'])
def submit_test_api():
    data = request.get_json() or {}
    paper_id = data.get('paper_id')
    time_taken = data.get('time_taken_seconds', 0)
    client_responses = data.get('responses', {})

    db = get_db()
    c = db.cursor()

    # Get paper specs
    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        return jsonify({"success": False, "error": "Invalid test paper ID"}), 400
    paper = dict(p_row)

    # Fetch all questions for this paper
    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (paper_id,))
    q_rows = c.fetchall()
    if not q_rows:
        c.execute("SELECT * FROM questions WHERE exam_code = ? ORDER BY id ASC", (paper['exam_code'],))
        q_rows = c.fetchall()

    questions = [dict(q) for q in q_rows]

    # Evaluate responses using exact marking scheme
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    calculated_score = 0.0

    topic_stats = {}
    verified_responses = {}

    for q in questions:
        q_id = str(q['id'])
        topic = q['topic']
        subject = q['subject']

        if topic not in topic_stats:
            topic_stats[topic] = {"subject": subject, "total": 0, "correct": 0, "accuracy": 0.0, "status": "Needs Improvement"}

        user_ans = None
        if q_id in client_responses:
            user_ans = client_responses[q_id].get('selectedOption')

        if user_ans:
            topic_stats[topic]['total'] += 1
            if user_ans == q['correct_option']:
                correct_count += 1
                calculated_score += paper['marks_per_correct']
                topic_stats[topic]['correct'] += 1
                is_correct = True
            else:
                incorrect_count += 1
                calculated_score -= paper['negative_marks']
                is_correct = False
            verified_responses[q_id] = {
                "selected": user_ans,
                "correct": q['correct_option'],
                "is_correct": is_correct
            }
        else:
            unattempted_count += 1
            verified_responses[q_id] = {
                "selected": None,
                "correct": q['correct_option'],
                "is_correct": False
            }

    # Accuracy calculations
    total_attempted = correct_count + incorrect_count
    accuracy_percent = round((correct_count / total_attempted * 100), 1) if total_attempted > 0 else 0.0
    calculated_score = round(max(0.0, calculated_score), 2)

    # Calculate status per topic
    for topic, stats in topic_stats.items():
        if stats['total'] > 0:
            acc = round((stats['correct'] / stats['total']) * 100, 1)
            stats['accuracy'] = acc
            if acc >= 70.0:
                stats['status'] = "Strong Performance"
            elif acc >= 50.0:
                stats['status'] = "Practice Recommended"
            else:
                stats['status'] = "Needs Improvement"
        else:
            stats['status'] = "Needs Improvement"

    # User binding: if logged in, save to user; otherwise fallback
    user_id = session.get('user_id')
    if not user_id:
        c.execute("SELECT id FROM users WHERE username = 'aspirant'")
        u_row = c.fetchone()
        user_id = u_row[0] if u_row else 1

    c.execute('''
    INSERT INTO test_attempts (
        user_id, paper_id, score, max_marks, total_questions,
        correct_count, incorrect_count, unattempted_count, accuracy_percent,
        time_taken_seconds, responses_json, topic_stats_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, paper_id, calculated_score, paper['max_marks'], len(questions),
        correct_count, incorrect_count, unattempted_count, accuracy_percent,
        time_taken, json.dumps(verified_responses), json.dumps(topic_stats)
    ))
    attempt_id = c.lastrowid

    # Enforce attempt entitlement consumption
    c.execute("SELECT free_attempt_used FROM users WHERE id = ?", (user_id,))
    u_row = c.fetchone()
    if u_row and u_row['free_attempt_used'] == 0:
        c.execute("UPDATE users SET free_attempt_used = 1 WHERE id = ?", (user_id,))
        c.execute('''
        INSERT INTO test_entitlements (user_id, paper_id, is_free_attempt, is_consumed, attempt_id, consumed_at)
        VALUES (?, ?, 1, 1, ?, CURRENT_TIMESTAMP)
        ''', (user_id, paper_id, attempt_id))
    else:
        c.execute('''
        UPDATE test_entitlements
        SET is_consumed = 1, attempt_id = ?, consumed_at = CURRENT_TIMESTAMP
        WHERE id = (
            SELECT id FROM test_entitlements 
            WHERE user_id = ? AND paper_id = ? AND is_consumed = 0 
            ORDER BY id ASC LIMIT 1
        )
        ''', (attempt_id, user_id, paper_id))

    db.commit()

    return jsonify({"success": True, "attempt_id": attempt_id})

@app.route('/test-result/<int:attempt_id>')
@login_required
def test_result_view(attempt_id):
    db = get_db()
    c = db.cursor()
    c.execute('''
    SELECT a.*, p.title as paper_title, p.exam_code, p.marks_per_correct, p.negative_marks, u.full_name as candidate_name
    FROM test_attempts a
    JOIN test_papers p ON a.paper_id = p.id
    JOIN users u ON a.user_id = u.id
    WHERE a.id = ?
    ''', (attempt_id,))
    attempt_row = c.fetchone()
    if not attempt_row:
        flash("Attempt record not found.", "warning")
        return redirect(url_for('tests_view'))

    attempt = dict(attempt_row)

    # Server-side IDOR authorization check
    current_user_id = session.get('user_id')
    current_role = session.get('role')
    if current_role != 'admin' and attempt['user_id'] != current_user_id:
        flash("Access Denied: You are not authorized to view another candidate's examination results.", "error")
        return redirect(url_for('dashboard'))

    responses = json.loads(attempt['responses_json'])
    topic_stats = json.loads(attempt['topic_stats_json'] or '{}')

    # Fetch questions for this paper
    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (attempt['paper_id'],))
    q_rows = c.fetchall()
    if not q_rows:
        c.execute("SELECT * FROM questions WHERE exam_code = ? ORDER BY id ASC", (attempt['exam_code'],))
        q_rows = c.fetchall()

    questions = [dict(q) for q in q_rows]
    review_items = []
    for q in questions:
        q_id = str(q['id'])
        u_resp = responses.get(q_id, {})
        review_items.append({
            "question": q,
            "user_selected": u_resp.get('selected'),
            "is_correct": u_resp.get('is_correct', False)
        })

    c.execute("SELECT * FROM test_papers WHERE id = ?", (attempt['paper_id'],))
    paper = dict(c.fetchone())

    return render_template(
        'test_result.html',
        attempt=attempt,
        paper=paper,
        candidate_name=attempt['candidate_name'],
        topic_stats=topic_stats,
        review_items=review_items
    )

@app.route('/download-paper-pdf/<int:paper_id>')
def download_paper_pdf_route(paper_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Paper not found", "error")
        return redirect(url_for('pyq_library'))
    paper = dict(p_row)

    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (paper_id,))
    q_rows = c.fetchall()
    if not q_rows:
        c.execute("SELECT * FROM questions WHERE exam_code = ? ORDER BY id ASC", (paper['exam_code'],))
        q_rows = c.fetchall()
    questions = [dict(q) for q in q_rows]

    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs'), exist_ok=True)
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs', f"defence_path_paper_{paper_id}.pdf")
    generate_paper_pdf(paper, questions, pdf_path)

    clean_filename = f"{paper['exam_code']}_{paper['paper_type']}_{paper['year'] or 'Practice'}.pdf".replace(" ", "_")
    return send_file(pdf_path, as_attachment=True, download_name=clean_filename)


# ==========================================
# STUDENT DASHBOARD & ANALYTICS
# ==========================================

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()

    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(c.fetchone())

    # User attempts
    c.execute('''
    SELECT a.*, p.title as paper_title
    FROM test_attempts a
    JOIN test_papers p ON a.paper_id = p.id
    WHERE a.user_id = ?
    ORDER BY a.attempt_date DESC LIMIT 5
    ''', (user_id,))
    attempts = [dict(a) for a in c.fetchall()]

    # Aggregate stats
    c.execute("SELECT COUNT(*), AVG(accuracy_percent), MAX(score) FROM test_attempts WHERE user_id = ?", (user_id,))
    agg = c.fetchone()
    total_attempts = agg[0] or 0
    avg_accuracy = round(agg[1] or 0.0, 1)

    # Tracked applications
    c.execute("SELECT * FROM application_tracker WHERE user_id = ? ORDER BY id DESC LIMIT 4", (user_id,))
    tracked_apps = [dict(t) for dict_t in [dict(t) for t in c.fetchall()] for t in [dict_t]]

    # Saved jobs
    c.execute('''
    SELECT r.* FROM recruitments r
    JOIN saved_jobs s ON r.id = s.recruitment_id
    WHERE s.user_id = ? ORDER BY s.saved_at DESC LIMIT 3
    ''', (user_id,))
    saved_jobs = [dict(j) for j in c.fetchall()]

    # Study planner tasks
    c.execute("SELECT * FROM study_planner WHERE user_id = ? ORDER BY is_completed ASC, target_date ASC LIMIT 5", (user_id,))
    study_tasks = [dict(t) for t in c.fetchall()]

    # Compile weak & strong topics from all attempts
    c.execute("SELECT topic_stats_json FROM test_attempts WHERE user_id = ?", (user_id,))
    all_topic_stats = {}
    for row in c.fetchall():
        if row[0]:
            try:
                t_dict = json.loads(row[0])
                for topic, stats in t_dict.items():
                    if topic not in all_topic_stats:
                        all_topic_stats[topic] = {"subject": stats.get('subject', 'General'), "total": 0, "correct": 0}
                    all_topic_stats[topic]['total'] += stats.get('total', 0)
                    all_topic_stats[topic]['correct'] += stats.get('correct', 0)
            except Exception:
                pass

    weak_topics = []
    strong_topics = []
    for topic, stats in all_topic_stats.items():
        if stats['total'] >= 1:
            acc = round((stats['correct'] / stats['total']) * 100, 1)
            item = {"topic": topic, "subject": stats['subject'], "accuracy": acc, "total": stats['total']}
            if acc < 50.0:
                weak_topics.append(item)
            elif acc >= 70.0:
                strong_topics.append(item)

    c.execute("SELECT COUNT(*) FROM application_tracker WHERE user_id = ?", (user_id,))
    tracked_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM study_planner WHERE user_id = ? AND is_completed = 0", (user_id,))
    pending_tasks = c.fetchone()[0]

    return render_template(
        'dashboard.html',
        user=user,
        attempts=attempts,
        total_attempts=total_attempts,
        avg_accuracy=avg_accuracy,
        tracked_apps=tracked_apps,
        tracked_count=tracked_count,
        saved_jobs=saved_jobs,
        study_tasks=study_tasks,
        pending_tasks=pending_tasks,
        weak_topics=weak_topics,
        strong_topics=strong_topics
    )

@app.route('/weakness-analysis')
@login_required
def weakness_analysis():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()

    c.execute("SELECT * FROM test_attempts WHERE user_id = ? ORDER BY attempt_date ASC", (user_id,))
    attempts = [dict(a) for a in c.fetchall()]

    all_topic_stats = {}
    subject_stats = {}

    for a in attempts:
        if a['topic_stats_json']:
            try:
                t_dict = json.loads(a['topic_stats_json'])
                for topic, s in t_dict.items():
                    subj = s.get('subject', 'General')
                    if topic not in all_topic_stats:
                        all_topic_stats[topic] = {"subject": subj, "total": 0, "correct": 0}
                    all_topic_stats[topic]['total'] += s.get('total', 0)
                    all_topic_stats[topic]['correct'] += s.get('correct', 0)

                    if subj not in subject_stats:
                        subject_stats[subj] = {"total": 0, "correct": 0}
                    subject_stats[subj]['total'] += s.get('total', 0)
                    subject_stats[subj]['correct'] += s.get('correct', 0)
            except Exception:
                pass

    for subj, s in subject_stats.items():
        s['accuracy'] = round((s['correct'] / s['total']) * 100, 1) if s['total'] > 0 else 0.0

    weak_list = []
    practice_list = []
    strong_list = []

    for topic, stats in all_topic_stats.items():
        if stats['total'] >= 1:
            acc = round((stats['correct'] / stats['total']) * 100, 1)
            item = {"topic": topic, "subject": stats['subject'], "accuracy": acc, "total": stats['total']}
            if acc < 50.0:
                weak_list.append(item)
            elif acc < 70.0:
                practice_list.append(item)
            else:
                strong_list.append(item)

    return render_template(
        'weakness.html',
        weak_list=weak_list,
        practice_list=practice_list,
        strong_list=strong_list,
        subject_stats_json=json.dumps(subject_stats),
        attempts_history_json=json.dumps(attempts)
    )

@app.route('/my-applications')
@login_required
def my_applications():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM application_tracker WHERE user_id = ? ORDER BY id DESC", (user_id,))
    applications = [dict(a) for a in c.fetchall()]
    return render_template('applications.html', applications=applications)

@app.route('/my-applications/save', methods=['POST'])
@login_required
def save_application():
    user_id = session.get('user_id')
    app_id = request.form.get('app_id')
    exam_name = request.form.get('exam_name')
    organization = request.form.get('organization')
    app_date = request.form.get('application_date')
    status = request.form.get('status')
    exam_date = request.form.get('exam_date')
    reference_number = request.form.get('reference_number')
    admit_card_status = request.form.get('admit_card_status')
    notes = request.form.get('notes')

    db = get_db()
    c = db.cursor()

    if app_id:
        c.execute('''
        UPDATE application_tracker
        SET exam_name = ?, organization = ?, application_date = ?, status = ?,
            exam_date = ?, reference_number = ?, admit_card_status = ?, notes = ?
        WHERE id = ? AND user_id = ?
        ''', (exam_name, organization, app_date, status, exam_date, reference_number, admit_card_status, notes, app_id, user_id))
        flash("Application record updated successfully.", "success")
    else:
        c.execute('''
        INSERT INTO application_tracker (
            user_id, exam_name, organization, application_date, status,
            exam_date, reference_number, admit_card_status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, exam_name, organization, app_date, status, exam_date, reference_number, admit_card_status, notes))
        flash("New application added to personal tracker.", "success")

    db.commit()
    return redirect(url_for('my_applications'))

@app.route('/my-applications/delete/<int:app_id>', methods=['POST'])
@login_required
def delete_application(app_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM application_tracker WHERE id = ? AND user_id = ?", (app_id, user_id))
    db.commit()
    flash("Application record removed.", "info")
    return redirect(url_for('my_applications'))

@app.route('/study-planner')
@login_required
def study_planner_view():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM study_planner WHERE user_id = ? ORDER BY is_completed ASC, target_date ASC", (user_id,))
    tasks = [dict(t) for t in c.fetchall()]
    return render_template('study_planner.html', tasks=tasks)

@app.route('/study-planner/add', methods=['POST'])
@login_required
def add_study_task():
    user_id = session.get('user_id')
    title = request.form.get('title')
    subject = request.form.get('subject')
    target_date = request.form.get('target_date')
    priority = request.form.get('priority', 'Medium')

    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO study_planner (user_id, title, subject, target_date, priority, is_completed)
    VALUES (?, ?, ?, ?, ?, 0)
    ''', (user_id, title, subject, target_date, priority))
    db.commit()
    flash("Milestone added to study schedule.", "success")
    return redirect(url_for('study_planner_view'))

@app.route('/study-planner/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_study_task(task_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE study_planner SET is_completed = 1 - is_completed WHERE id = ? AND user_id = ?", (task_id, user_id))
    db.commit()
    return redirect(url_for('study_planner_view'))

@app.route('/study-planner/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_study_task(task_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM study_planner WHERE id = ? AND user_id = ?", (task_id, user_id))
    db.commit()
    flash("Study task removed.", "info")
    return redirect(url_for('study_planner_view'))

@app.route('/saved-jobs')
@login_required
def saved_jobs_view():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute('''
    SELECT r.* FROM recruitments r
    JOIN saved_jobs s ON r.id = s.recruitment_id
    WHERE s.user_id = ? ORDER BY s.saved_at DESC
    ''', (user_id,))
    jobs = [dict(j) for j in c.fetchall()]
    return render_template('saved_jobs.html', jobs=jobs)

@app.route('/save-job/<int:job_id>', methods=['POST'])
@login_required
def save_job_route(job_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    try:
        c.execute("INSERT INTO saved_jobs (user_id, recruitment_id) VALUES (?, ?)", (user_id, job_id))
        db.commit()
        flash("Recruitment notice bookmarked to your dossier.", "success")
    except sqlite3.IntegrityError:
        flash("Notice is already bookmarked.", "info")
    return redirect(request.referrer or url_for('jobs_view'))

@app.route('/unsave-job/<int:job_id>', methods=['POST'])
@login_required
def unsave_job_route(job_id):
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM saved_jobs WHERE user_id = ? AND recruitment_id = ?", (user_id, job_id))
    db.commit()
    flash("Notice removed from saved dossier.", "info")
    return redirect(url_for('saved_jobs_view'))

@app.route('/profile')
@login_required
def profile_view():
    user_id = session.get('user_id')
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = dict(c.fetchone())
    return render_template('profile.html', user=user)

@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    user_id = session.get('user_id')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    target_exam = request.form.get('target_exam')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')

    db = get_db()
    c = db.cursor()

    if new_password:
        if new_password != confirm_new_password:
            flash("New passwords do not match.", "error")
            return redirect(url_for('profile_view'))
        p_hash = generate_password_hash(new_password)
        c.execute('''
        UPDATE users SET full_name = ?, email = ?, phone = ?, target_exam = ?, password_hash = ?
        WHERE id = ?
        ''', (full_name, email, phone, target_exam, p_hash, user_id))
    else:
        c.execute('''
        UPDATE users SET full_name = ?, email = ?, phone = ?, target_exam = ?
        WHERE id = ?
        ''', (full_name, email, phone, target_exam, user_id))

    db.commit()
    session['full_name'] = full_name
    flash("Cadet profile updated successfully.", "success")
    return redirect(url_for('profile_view'))


# ==========================================
# DEVELOPER & CONTACT ROUTES
# ==========================================

@app.route('/developer-profile')
def developer_profile_view():
    return render_template('developer.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact_view():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        ip_addr = request.remote_addr

        if not name or not email or not message:
            flash("Please fill in all mandatory fields.", "error")
            return redirect(url_for('contact_view'))

        db = get_db()
        c = db.cursor()
        c.execute('''
        INSERT INTO contact_messages (name, email, subject, message, ip_address)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, email, subject, message, ip_addr))
        db.commit()

        flash("Your message has been transmitted successfully to Project Developer Er. Prashant Mishra.", "success")
        return redirect(url_for('contact_view'))

    return render_template('contact.html')

@app.route('/about')
def about_view():
    return render_template('about.html')




# ==========================================
# AUTHENTICATION: LOGIN, REGISTER & ADMIN GATEWAY
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login_view():
    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        client_ip = request.remote_addr or 'unknown'

        if is_rate_limited(client_ip) or is_rate_limited(identifier):
            flash("Too many failed authentication attempts. Access temporarily locked for 5 minutes.", "error")
            return render_template('login.html')

        if not identifier or not password:
            flash("Please provide both username/email and password.", "error")
            return render_template('login.html')

        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier))
        user_row = c.fetchone()

        if user_row and check_password_hash(user_row['password_hash'], password):
            clear_failed_attempts(client_ip)
            clear_failed_attempts(identifier)
            
            session.clear()
            session['user_id'] = user_row['id']
            session['username'] = user_row['username']
            session['full_name'] = user_row['full_name']
            session['role'] = user_row['role']
            session['profile_image'] = user_row['profile_image']

            flash(f"Welcome to Defence Path Portal, {user_row['full_name']}.", "success")
            next_url = request.args.get('next')
            if user_row['role'] == 'admin':
                return redirect(next_url or url_for('admin_dashboard'))
            return redirect(next_url or url_for('dashboard'))
        else:
            record_failed_attempt(client_ip)
            record_failed_attempt(identifier)
            flash("Invalid authentication credentials. Please verify username and password.", "error")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_view():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_pass = request.form.get('confirm_password', '')
        target_exam = request.form.get('target_exam', 'UPSC NDA & NA')

        # Strict Server-Side Validation
        if not full_name or len(full_name) < 2 or len(full_name) > 80:
            flash("Full name must be between 2 and 80 characters.", "error")
            return redirect(url_for('login_view'))

        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            flash("Username must be 3-30 characters alphanumeric (letters, numbers, underscores only).", "error")
            return redirect(url_for('login_view'))

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash("Please provide a valid email address.", "error")
            return redirect(url_for('login_view'))

        if len(password) < 6:
            flash("Password must be at least 6 characters in length.", "error")
            return redirect(url_for('login_view'))

        if password != confirm_pass:
            flash("Passwords do not match.", "error")
            return redirect(url_for('login_view'))

        db = get_db()
        c = db.cursor()
        c.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if c.fetchone():
            flash("Username or Email already registered in the system.", "warning")
            return redirect(url_for('login_view'))

        p_hash = generate_password_hash(password)
        # Enforce student role on all public registrations
        c.execute('''
        INSERT INTO users (username, full_name, email, password_hash, target_exam, role)
        VALUES (?, ?, ?, ?, ?, 'student')
        ''', (username, full_name, email, p_hash, target_exam))
        db.commit()

        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        new_user = c.fetchone()

        session.clear()
        session['user_id'] = new_user['id']
        session['username'] = new_user['username']
        session['full_name'] = new_user['full_name']
        session['role'] = new_user['role']
        session['profile_image'] = new_user['profile_image']

        flash("Aspirant profile registered successfully! Welcome to Defence Path.", "success")
        return redirect(url_for('dashboard'))

    return redirect(url_for('login_view'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('user_id') and session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        client_ip = request.remote_addr or 'unknown'

        if is_rate_limited(f"admin_{client_ip}") or is_rate_limited(f"admin_{identifier}"):
            flash("Too many failed administrative attempts. Gateway locked for 5 minutes.", "error")
            return render_template('admin/login.html')

        if not identifier or not password:
            flash("Please provide administrative credentials.", "error")
            return render_template('admin/login.html')

        # Safe alias mapping: legacy 'admin' maps to admin email
        lookup_identifier = identifier.strip()
        if lookup_identifier.lower() == 'admin':
            lookup_identifier = 'admin@defencepath.in'

        db = get_db()
        c = db.cursor()
        c.execute("""
            SELECT * FROM users 
            WHERE (email = ? OR username = ? OR (role = 'admin' AND ? = 'admin')) 
              AND role = 'admin'
        """, (lookup_identifier, lookup_identifier, identifier))
        admin_row = c.fetchone()

        if admin_row and check_password_hash(admin_row['password_hash'], password):
            clear_failed_attempts(f"admin_{client_ip}")
            clear_failed_attempts(f"admin_{identifier}")
            
            # Regenerate session securely
            session.clear()
            session['user_id'] = admin_row['id']
            session['username'] = admin_row['username']
            session['email'] = admin_row['email']
            session['full_name'] = admin_row['full_name']
            session['role'] = admin_row['role']
            session['profile_image'] = admin_row['profile_image']

            flash(f"Administrator Command verified. Welcome, {admin_row['full_name']}.", "success")
            next_url = request.args.get('next')
            return redirect(next_url or url_for('admin_dashboard'))
        else:
            record_failed_attempt(f"admin_{client_ip}")
            record_failed_attempt(f"admin_{identifier}")
            flash("Invalid administrator credentials or unauthorized role.", "error")

    return render_template('admin/login.html')

@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_first_time_setup():
    csrf_token = get_or_create_csrf()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        client_ip = request.remote_addr or 'unknown'

        if not email:
            flash("Please enter the administrator registered email address.", "error")
            return render_template('admin/first_time_setup.html', csrf_token=csrf_token)

        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND role = 'admin'", (email,))
        admin_user = c.fetchone()

        if admin_user and admin_user['first_time_setup_done'] == 1:
            flash("First-time administrator setup has already been completed for this account. Please use Administrator Login or Password Recovery.", "warning")
            return redirect(url_for('admin_login'))

        limited, msg = is_otp_rate_limited(f"otp_{email}")
        if limited:
            flash(msg, "warning")
            return render_template('admin/first_time_setup.html', csrf_token=csrf_token)

        if not admin_user:
            flash("If this email address is an authorized administrator account eligible for initial setup, a verification code has been dispatched.", "info")
            session['setup_email'] = email
            return redirect(url_for('admin_setup_verify'))

        # Check SMTP configuration
        if not email_service.is_smtp_configured() and not app.config.get('TESTING'):
            flash("Email service is currently unconfigured on this server. Please configure SMTP credentials in .env or contact the system administrator.", "error")
            return render_template('admin/first_time_setup.html', csrf_token=csrf_token)

        # Invalidate any prior unused setup OTPs for this user
        c.execute("""
            UPDATE password_resets 
            SET used_at = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND purpose = 'first_time_setup' AND used_at IS NULL
        """, (admin_user['id'],))

        otp = generate_secure_otp()
        otp_h = hash_token(otp)
        expires = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

        c.execute("""
            INSERT INTO password_resets (user_id, email, purpose, otp_hash, expires_at)
            VALUES (?, ?, 'first_time_setup', ?, ?)
        """, (admin_user['id'], email, otp_h, expires))
        db.commit()

        record_otp_request(f"otp_{email}")
        record_otp_request(f"otp_ip_{client_ip}")

        if app.config.get('TESTING'):
            session['test_last_otp'] = otp

        # Dispatch Email
        sent, err_msg = email_service.send_otp_email(
            recipient_email=email,
            otp_code=otp,
            purpose="Administrator First-Time Setup",
            recipient_name=admin_user['full_name']
        )

        if not sent and not app.config.get('TESTING'):
            flash(err_msg, "error")
            return render_template('admin/first_time_setup.html', csrf_token=csrf_token)

        session['setup_email'] = email
        session['setup_user_id'] = admin_user['id']
        flash("A 6-digit verification code has been dispatched to your administrator email address. Code expires in 5 minutes.", "success")
        return redirect(url_for('admin_setup_verify'))

    return render_template('admin/first_time_setup.html', csrf_token=csrf_token)

@app.route('/admin/setup/verify', methods=['GET', 'POST'])
def admin_setup_verify():
    email = session.get('setup_email')
    user_id = session.get('setup_user_id')
    if not email:
        flash("Setup session expired or invalid. Please initiate administrator setup again.", "error")
        return redirect(url_for('admin_first_time_setup'))

    csrf_token = get_or_create_csrf()

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()

        if not otp or len(otp) != 6 or not otp.isdigit():
            flash("Please provide a valid 6-digit numeric verification code.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('admin_setup_verify'),
                                   resend_action=url_for('admin_first_time_setup'),
                                   login_url=url_for('admin_login'))

        if not user_id:
            flash("Invalid or expired verification code.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('admin_setup_verify'),
                                   resend_action=url_for('admin_first_time_setup'),
                                   login_url=url_for('admin_login'))

        db = get_db()
        c = db.cursor()
        c.execute("""
            SELECT * FROM password_resets 
            WHERE user_id = ? AND purpose = 'first_time_setup' AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        reset_record = c.fetchone()

        if not reset_record:
            flash("No active verification code found. Please request a new code.", "error")
            return redirect(url_for('admin_first_time_setup'))

        # Check expiry
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if reset_record['expires_at'] < now_str:
            c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
            db.commit()
            flash("Verification code has expired. Please request a new code.", "error")
            return redirect(url_for('admin_first_time_setup'))

        # Check attempts limit
        if reset_record['attempts'] >= 3:
            c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
            db.commit()
            flash("Too many failed attempts. This verification code has been revoked. Please request a new code.", "error")
            return redirect(url_for('admin_first_time_setup'))

        # Compare hash in constant time
        submitted_hash = hash_token(otp)
        if not hmac.compare_digest(reset_record['otp_hash'], submitted_hash):
            c.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?", (reset_record['id'],))
            db.commit()
            remaining = 2 - reset_record['attempts']
            if remaining <= 0:
                c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
                db.commit()
                flash("Too many failed attempts. This code has been revoked. Please request a new code.", "error")
                return redirect(url_for('admin_first_time_setup'))
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('admin_setup_verify'),
                                   resend_action=url_for('admin_first_time_setup'),
                                   login_url=url_for('admin_login'))

        # Valid OTP! Issue single-use password creation token
        setup_token = secrets.token_urlsafe(32)
        token_hash = hash_token(setup_token)
        c.execute("UPDATE password_resets SET reset_token_hash = ? WHERE id = ?", (token_hash, reset_record['id']))
        db.commit()

        session['setup_token'] = setup_token
        session['setup_record_id'] = reset_record['id']
        flash("Verification successful! Please establish your new master administrator password.", "success")
        return redirect(url_for('admin_setup_new_password'))

    return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                           verify_action=url_for('admin_setup_verify'),
                           resend_action=url_for('admin_first_time_setup'),
                           login_url=url_for('admin_login'))

@app.route('/admin/setup/new-password', methods=['GET', 'POST'])
def admin_setup_new_password():
    email = session.get('setup_email')
    user_id = session.get('setup_user_id')
    setup_token = session.get('setup_token')
    record_id = session.get('setup_record_id')

    if not email or not user_id or not setup_token or not record_id:
        flash("Session expired or unauthorized access. Please initiate setup again.", "error")
        return redirect(url_for('admin_first_time_setup'))

    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT * FROM password_resets 
        WHERE id = ? AND user_id = ? AND purpose = 'first_time_setup' AND used_at IS NULL
    """, (record_id, user_id))
    record = c.fetchone()

    if not record or not hmac.compare_digest(record['reset_token_hash'], hash_token(setup_token)):
        flash("Invalid or expired session token. Please initiate setup again.", "error")
        return redirect(url_for('admin_first_time_setup'))

    csrf_token = get_or_create_csrf()

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(password) < 8:
            flash("Administrator password must be at least 8 characters in length.", "error")
            return render_template('reset_password.html', target_email=email, is_admin=True, csrf_token=csrf_token,
                                   reset_action=url_for('admin_setup_new_password'), login_url=url_for('admin_login'))

        if password != confirm_password:
            flash("Passwords do not match. Please verify and re-enter.", "error")
            return render_template('reset_password.html', target_email=email, is_admin=True, csrf_token=csrf_token,
                                   reset_action=url_for('admin_setup_new_password'), login_url=url_for('admin_login'))

        # Save secure password hash and mark setup completed
        p_hash = generate_password_hash(password)
        c.execute("""
            UPDATE users 
            SET username = ?, password_hash = ?, first_time_setup_done = 1 
            WHERE id = ? AND role = 'admin'
        """, (email, p_hash, user_id))

        # Invalidate reset token and OTP record immediately
        c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (record_id,))
        c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE user_id = ? AND used_at IS NULL", (user_id,))
        db.commit()

        # Clean session
        session.pop('setup_email', None)
        session.pop('setup_user_id', None)
        session.pop('setup_token', None)
        session.pop('setup_record_id', None)

        flash("Master administrator password established successfully! Please log in using your registered email and password.", "success")
        return redirect(url_for('admin_login'))

    return render_template('reset_password.html', target_email=email, is_admin=True, csrf_token=csrf_token,
                           reset_action=url_for('admin_setup_new_password'), login_url=url_for('admin_login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password_view():
    requested_role = request.args.get('role', request.form.get('role', '')).strip().lower()
    csrf_token = get_or_create_csrf()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        client_ip = request.remote_addr or 'unknown'

        if not email:
            flash("Please enter your registered email address.", "error")
            return render_template('forgot_password.html', role=requested_role, csrf_token=csrf_token)

        limited, msg = is_otp_rate_limited(f"otp_{email}")
        if limited:
            flash(msg, "warning")
            return render_template('forgot_password.html', role=requested_role, csrf_token=csrf_token)

        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user_row = c.fetchone()

        success_msg = "If an account exists for this email address, a 6-digit recovery code has been dispatched. Code expires in 5 minutes."

        if not user_row:
            record_otp_request(f"otp_{email}")
            record_otp_request(f"otp_ip_{client_ip}")
            session['pwd_recovery_email'] = email
            session['pwd_recovery_role'] = requested_role
            flash(success_msg, "info")
            return redirect(url_for('forgot_password_verify'))

        # Check SMTP configuration
        if not email_service.is_smtp_configured() and not app.config.get('TESTING'):
            flash("Email recovery service is currently unconfigured on this server. Please contact the system administrator.", "error")
            return render_template('forgot_password.html', role=requested_role, csrf_token=csrf_token)

        # Invalidate any prior unused OTPs for this user
        c.execute("""
            UPDATE password_resets 
            SET used_at = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND purpose = 'forgot_password' AND used_at IS NULL
        """, (user_row['id'],))

        otp = generate_secure_otp()
        otp_h = hash_token(otp)
        expires = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

        c.execute("""
            INSERT INTO password_resets (user_id, email, purpose, otp_hash, expires_at)
            VALUES (?, ?, 'forgot_password', ?, ?)
        """, (user_row['id'], email, otp_h, expires))
        db.commit()

        record_otp_request(f"otp_{email}")
        record_otp_request(f"otp_ip_{client_ip}")

        if app.config.get('TESTING'):
            session['test_last_otp'] = otp

        # Dispatch email
        sent, err_msg = email_service.send_otp_email(
            recipient_email=email,
            otp_code=otp,
            purpose="Password Recovery",
            recipient_name=user_row['full_name']
        )

        if not sent and not app.config.get('TESTING'):
            flash(err_msg, "error")
            return render_template('forgot_password.html', role=requested_role, csrf_token=csrf_token)

        session['pwd_recovery_email'] = email
        session['pwd_recovery_user_id'] = user_row['id']
        session['pwd_recovery_role'] = user_row['role']
        flash(success_msg, "success")
        return redirect(url_for('forgot_password_verify'))

    return render_template('forgot_password.html', role=requested_role, csrf_token=csrf_token)

@app.route('/forgot-password/verify', methods=['GET', 'POST'])
def forgot_password_verify():
    email = session.get('pwd_recovery_email')
    user_id = session.get('pwd_recovery_user_id')
    role = session.get('pwd_recovery_role', '')

    login_url = url_for('admin_login') if role == 'admin' else url_for('login_view')
    resend_url = url_for('forgot_password_view', role='admin') if role == 'admin' else url_for('forgot_password_view')

    if not email:
        flash("Password recovery session expired. Please enter your email again.", "error")
        return redirect(resend_url)

    csrf_token = get_or_create_csrf()

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()

        if not otp or len(otp) != 6 or not otp.isdigit():
            flash("Please enter a valid 6-digit numeric verification code.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('forgot_password_verify'),
                                   resend_action=resend_url, login_url=login_url)

        if not user_id:
            flash("Invalid or expired verification code.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('forgot_password_verify'),
                                   resend_action=resend_url, login_url=login_url)

        db = get_db()
        c = db.cursor()
        c.execute("""
            SELECT * FROM password_resets 
            WHERE user_id = ? AND purpose = 'forgot_password' AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        reset_record = c.fetchone()

        if not reset_record:
            flash("No active recovery request found. Please request a new verification code.", "error")
            return redirect(resend_url)

        # Check expiry
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if reset_record['expires_at'] < now_str:
            c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
            db.commit()
            flash("Verification code has expired (5-minute limit). Please request a new code.", "error")
            return redirect(resend_url)

        # Check attempts
        if reset_record['attempts'] >= 3:
            c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
            db.commit()
            flash("Too many failed attempts. This verification code has been revoked. Please request a new code.", "error")
            return redirect(resend_url)

        # Compare hash
        submitted_hash = hash_token(otp)
        if not hmac.compare_digest(reset_record['otp_hash'], submitted_hash):
            c.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?", (reset_record['id'],))
            db.commit()
            remaining = 2 - reset_record['attempts']
            if remaining <= 0:
                c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (reset_record['id'],))
                db.commit()
                flash("Too many failed attempts. This verification code has been revoked.", "error")
                return redirect(resend_url)
            flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "error")
            return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                                   verify_action=url_for('forgot_password_verify'),
                                   resend_action=resend_url, login_url=login_url)

        # Valid OTP! Issue single-use reset token
        reset_token = secrets.token_urlsafe(32)
        token_h = hash_token(reset_token)
        c.execute("UPDATE password_resets SET reset_token_hash = ? WHERE id = ?", (token_h, reset_record['id']))
        db.commit()

        session['pwd_reset_token'] = reset_token
        session['pwd_reset_record_id'] = reset_record['id']
        flash("Verification code confirmed. You may now create your new password.", "success")
        return redirect(url_for('forgot_password_reset'))

    return render_template('verify_otp.html', target_email=email, csrf_token=csrf_token,
                           verify_action=url_for('forgot_password_verify'),
                           resend_action=resend_url, login_url=login_url)

@app.route('/forgot-password/reset', methods=['GET', 'POST'])
def forgot_password_reset():
    email = session.get('pwd_recovery_email')
    user_id = session.get('pwd_recovery_user_id')
    role = session.get('pwd_recovery_role', '')
    token = session.get('pwd_reset_token')
    record_id = session.get('pwd_reset_record_id')

    login_url = url_for('admin_login') if role == 'admin' else url_for('login_view')

    if not email or not user_id or not token or not record_id:
        flash("Session expired or unauthorized request. Please restart password recovery.", "error")
        return redirect(url_for('forgot_password_view'))

    db = get_db()
    c = db.cursor()
    c.execute("""
        SELECT * FROM password_resets 
        WHERE id = ? AND user_id = ? AND purpose = 'forgot_password' AND used_at IS NULL
    """, (record_id, user_id))
    record = c.fetchone()

    if not record or not hmac.compare_digest(record['reset_token_hash'], hash_token(token)):
        flash("Invalid or expired reset token. Please restart password recovery.", "error")
        return redirect(url_for('forgot_password_view'))

    csrf_token = get_or_create_csrf()
    is_admin = (role == 'admin')

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        min_len = 8 if is_admin else 6
        if len(password) < min_len:
            flash(f"Password must be at least {min_len} characters in length.", "error")
            return render_template('reset_password.html', target_email=email, is_admin=is_admin, csrf_token=csrf_token,
                                   reset_action=url_for('forgot_password_reset'), login_url=login_url)

        if password != confirm_password:
            flash("Passwords do not match. Please verify and re-enter.", "error")
            return render_template('reset_password.html', target_email=email, is_admin=is_admin, csrf_token=csrf_token,
                                   reset_action=url_for('forgot_password_reset'), login_url=login_url)

        # Save secure password hash
        p_hash = generate_password_hash(password)
        if is_admin:
            c.execute("UPDATE users SET password_hash = ?, first_time_setup_done = 1 WHERE id = ?", (p_hash, user_id))
        else:
            c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (p_hash, user_id))

        # Invalidate reset token and OTP immediately
        c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (record_id,))
        c.execute("UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE user_id = ? AND used_at IS NULL", (user_id,))
        db.commit()

        # Clear recovery session
        session.pop('pwd_recovery_email', None)
        session.pop('pwd_recovery_user_id', None)
        session.pop('pwd_recovery_role', None)
        session.pop('pwd_reset_token', None)
        session.pop('pwd_reset_record_id', None)

        flash("Password successfully reset! Please sign in with your new credentials.", "success")
        return redirect(login_url)

    return render_template('reset_password.html', target_email=email, is_admin=is_admin, csrf_token=csrf_token,
                           reset_action=url_for('forgot_password_reset'), login_url=login_url)

@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully signed out of Defence Path Command.", "info")
    return redirect(url_for('home'))


# ==========================================
# ADMINISTRATOR ROUTES
# ==========================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM recruitments")
    count_jobs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    count_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM test_papers")
    count_papers = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM contact_messages")
    count_messages = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM test_attempts")
    count_attempts = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM payment_transactions WHERE status = 'Pending'")
    count_pending_payments = c.fetchone()[0]

    c.execute("SELECT * FROM contact_messages ORDER BY id DESC LIMIT 5")
    messages = [dict(m) for m in c.fetchall()]

    c.execute('''
    SELECT a.*, u.full_name, u.username, p.title as paper_title, p.exam_code
    FROM test_attempts a
    JOIN users u ON a.user_id = u.id
    JOIN test_papers p ON a.paper_id = p.id
    ORDER BY a.attempt_date DESC LIMIT 6
    ''')
    recent_attempts = [dict(a) for a in c.fetchall()]

    return render_template(
        'admin/dashboard.html',
        count_jobs=count_jobs,
        count_users=count_users,
        count_papers=count_papers,
        count_messages=count_messages,
        count_attempts=count_attempts,
        count_pending_payments=count_pending_payments,
        messages=messages,
        recent_attempts=recent_attempts
    )

@app.route('/admin/developer-profile')
@admin_required
def admin_developer_profile():
    return render_template('admin/developer_profile.html')

@app.route('/admin/developer-profile/update', methods=['POST'])
@admin_required
def admin_developer_profile_update():
    name = request.form.get('name')
    title = request.form.get('title')
    contact_number = request.form.get('contact_number')
    email = request.form.get('email', '').strip() or None
    qualification = request.form.get('qualification')
    portfolio_url = request.form.get('portfolio_url')
    bio = request.form.get('bio')

    # Handle optional image file replacement
    uploaded_image_file = request.files.get('profile_image_file')
    profile_image_path = None

    if uploaded_image_file and uploaded_image_file.filename:
        filename = secure_filename(uploaded_image_file.filename)
        save_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'developer')
        os.makedirs(save_dir, exist_ok=True)
        dest_path = os.path.join(save_dir, filename)
        uploaded_image_file.save(dest_path)
        profile_image_path = f"/static/uploads/developer/{filename}"

    db = get_db()
    c = db.cursor()

    if profile_image_path:
        c.execute('''
        UPDATE developer_profile
        SET name = ?, title = ?, contact_number = ?, email = ?, qualification = ?,
            portfolio_url = ?, bio = ?, profile_image = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = (SELECT id FROM developer_profile ORDER BY id DESC LIMIT 1)
        ''', (name, title, contact_number, email, qualification, portfolio_url, bio, profile_image_path))
    else:
        c.execute('''
        UPDATE developer_profile
        SET name = ?, title = ?, contact_number = ?, email = ?, qualification = ?,
            portfolio_url = ?, bio = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = (SELECT id FROM developer_profile ORDER BY id DESC LIMIT 1)
        ''', (name, title, contact_number, email, qualification, portfolio_url, bio))

    db.commit()
    flash("Project Developer Profile updated successfully in persistent database.", "success")
    return redirect(url_for('admin_developer_profile'))

@app.route('/admin/recruitments')
@admin_required
def admin_recruitments():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM recruitments ORDER BY id DESC")
    recruitments = [dict(r) for r in c.fetchall()]
    return render_template('admin/recruitments.html', recruitments=recruitments)

@app.route('/admin/recruitments/add', methods=['POST'])
@admin_required
def admin_add_recruitment():
    title = request.form.get('title')
    organization = request.form.get('organization')
    post_name = request.form.get('post_name')
    category = request.form.get('category')
    min_age = float(request.form.get('min_age', 17.5))
    max_age = float(request.form.get('max_age', 21.0))
    qualification = request.form.get('qualification')
    start_date = request.form.get('start_date')
    closing_date = request.form.get('closing_date')
    status = request.form.get('status')
    application_url = request.form.get('application_url')
    notification_pdf_url = request.form.get('notification_pdf_url')

    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO recruitments (
        title, organization, post_name, category, min_age, max_age,
        qualification, start_date, closing_date, status,
        application_url, notification_pdf_url, source_name, last_verified, is_demo
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Admin Verified Source', ?, 1)
    ''', (title, organization, post_name, category, min_age, max_age, qualification, start_date, closing_date, status, application_url, notification_pdf_url, datetime.now().strftime("%d-%b-%Y")))
    db.commit()

    flash("New recruitment notice published.", "success")
    return redirect(url_for('admin_recruitments'))

@app.route('/admin/recruitments/delete/<int:rec_id>', methods=['POST'])
@admin_required
def admin_delete_recruitment(rec_id):
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM recruitments WHERE id = ?", (rec_id,))
    db.commit()
    flash("Recruitment notice deleted.", "info")
    return redirect(url_for('admin_recruitments'))

@app.route('/admin/pyqs')
@admin_required
def admin_pyqs():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers ORDER BY id ASC")
    papers = [dict(p) for p in c.fetchall()]
    return render_template('admin/pyqs.html', papers=papers)

@app.route('/admin/questions/add', methods=['POST'])
@admin_required
def admin_add_question():
    paper_id = request.form.get('paper_id')
    subject = request.form.get('subject')
    topic = request.form.get('topic')
    question_text_en = request.form.get('question_text_en')
    question_text_hi = request.form.get('question_text_hi')
    option_a_en = request.form.get('option_a_en')
    option_b_en = request.form.get('option_b_en')
    option_c_en = request.form.get('option_c_en')
    option_d_en = request.form.get('option_d_en')
    correct_option = request.form.get('correct_option')
    difficulty = request.form.get('difficulty', 'Moderate')
    explanation_en = request.form.get('explanation_en')

    db = get_db()
    c = db.cursor()
    c.execute("SELECT exam_code FROM test_papers WHERE id = ?", (paper_id,))
    p = c.fetchone()
    exam_code = p[0] if p else "NDA"

    c.execute('''
    INSERT INTO questions (
        paper_id, exam_code, subject, topic, difficulty,
        question_text_en, question_text_hi,
        option_a_en, option_a_hi,
        option_b_en, option_b_hi,
        option_c_en, option_c_hi,
        option_d_en, option_d_hi,
        correct_option, explanation_en
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        paper_id, exam_code, subject, topic, difficulty,
        question_text_en, question_text_hi,
        option_a_en, option_a_en,
        option_b_en, option_b_en,
        option_c_en, option_c_en,
        option_d_en, option_d_en,
        correct_option, explanation_en
    ))
    db.commit()

    flash("New question with detailed explanation added to Question Bank.", "success")
    return redirect(url_for('admin_pyqs'))

@app.route('/admin/announcements/add', methods=['POST'])
@admin_required
def admin_add_announcement():
    title = request.form.get('title')
    content = request.form.get('content')
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO announcements (title, category, content) VALUES (?, 'Update', ?)", (title, content))
    db.commit()
    flash("Announcement broadcasted successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    c = db.cursor()
    c.execute('''
    SELECT u.*, 
           COUNT(a.id) as attempts_count,
           MAX(a.attempt_date) as last_attempt_date,
           ROUND(AVG(a.accuracy_percent), 1) as avg_accuracy
    FROM users u
    LEFT JOIN test_attempts a ON u.id = a.user_id
    GROUP BY u.id
    ORDER BY u.id ASC
    ''')
    users = [dict(u) for u in c.fetchall()]
    return render_template('admin/users.html', users=users)

@app.route('/admin/student-results')
@admin_required
def admin_student_results():
    db = get_db()
    c = db.cursor()
    search_q = request.args.get('q', '').strip()
    paper_filter = request.args.get('paper_id', '').strip()
    student_filter = request.args.get('user_id', '').strip()

    query = '''
    SELECT a.*, u.username, u.full_name, u.email, p.title as paper_title, p.exam_code, p.paper_type, p.subject
    FROM test_attempts a
    JOIN users u ON a.user_id = u.id
    JOIN test_papers p ON a.paper_id = p.id
    WHERE 1=1
    '''
    params = []
    if search_q:
        query += " AND (u.full_name LIKE ? OR u.username LIKE ? OR u.email LIKE ? OR p.title LIKE ?)"
        like_val = f"%{search_q}%"
        params.extend([like_val, like_val, like_val, like_val])
    if paper_filter:
        query += " AND a.paper_id = ?"
        params.append(paper_filter)
    if student_filter:
        query += " AND a.user_id = ?"
        params.append(student_filter)

    query += " ORDER BY a.attempt_date DESC"
    c.execute(query, params)
    results = [dict(r) for r in c.fetchall()]

    # Test papers for dropdown filter
    c.execute("SELECT id, title, exam_code FROM test_papers ORDER BY title ASC")
    all_papers = [dict(p) for p in c.fetchall()]

    # Registered students for dropdown filter
    c.execute("SELECT id, username, full_name FROM users WHERE role = 'student' ORDER BY full_name ASC")
    all_students = [dict(s) for s in c.fetchall()]

    return render_template(
        'admin/student_results.html',
        results=results,
        all_papers=all_papers,
        all_students=all_students,
        search_q=search_q,
        selected_paper=paper_filter,
        selected_student=student_filter
    )


# ==========================================
# ADMIN CMS: PAYMENTS, EXAMS, SYLLABUS, IMPORT & AUDIT
# ==========================================

@app.route('/admin/payments')
@admin_required
def admin_payments():
    db = get_db()
    c = db.cursor()
    selected_status = request.args.get('status', '').strip()

    sql = '''
    SELECT pt.*, u.full_name, u.username, u.email, tp.title as paper_title, tp.exam_code, tp.paper_type
    FROM payment_transactions pt
    JOIN users u ON pt.user_id = u.id
    JOIN test_papers tp ON pt.paper_id = tp.id
    '''
    params = []
    if selected_status:
        sql += " WHERE pt.status = ?"
        params.append(selected_status)
    sql += " ORDER BY pt.id DESC"

    c.execute(sql, params)
    payments = [dict(p) for p in c.fetchall()]

    c.execute("SELECT COUNT(*) FROM payment_transactions")
    total_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payment_transactions WHERE status = 'Pending'")
    pending_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payment_transactions WHERE status = 'Verified'")
    verified_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payment_transactions WHERE status = 'Rejected'")
    rejected_count = c.fetchone()[0]

    return render_template(
        'admin/payments.html',
        payments=payments,
        selected_status=selected_status,
        total_count=total_count,
        pending_count=pending_count,
        verified_count=verified_count,
        rejected_count=rejected_count
    )

@app.route('/admin/payments/verify/<int:payment_id>', methods=['POST'])
@admin_required
def admin_verify_payment(payment_id):
    db = get_db()
    c = db.cursor()
    admin_id = session.get('user_id')
    admin_username = session.get('username')

    c.execute("SELECT * FROM payment_transactions WHERE id = ?", (payment_id,))
    pay = c.fetchone()
    if not pay:
        flash("Transaction not found.", "error")
        return redirect(url_for('admin_payments'))

    c.execute('''
    UPDATE payment_transactions
    SET status = 'Verified', verified_by = ?, verified_at = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (admin_id, payment_id))

    c.execute('''
    INSERT INTO test_entitlements (user_id, paper_id, payment_id, is_free_attempt, is_consumed)
    VALUES (?, ?, ?, 0, 0)
    ''', (pay['user_id'], pay['paper_id'], payment_id))
    db.commit()

    database.log_admin_action(
        admin_id=admin_id,
        admin_username=admin_username,
        action="VERIFY_PAYMENT",
        target_type="payment",
        target_id=payment_id,
        details=f"Verified UPI Ref {pay['transaction_ref']} for test #{pay['paper_id']} and granted attempt entitlement.",
        ip_address=request.remote_addr,
        conn=db
    )

    flash(f"Payment reference '{pay['transaction_ref']}' verified! Candidate test attempt has been unlocked.", "success")
    return redirect(url_for('admin_payments'))

@app.route('/admin/payments/reject/<int:payment_id>', methods=['POST'])
@admin_required
def admin_reject_payment(payment_id):
    db = get_db()
    c = db.cursor()
    admin_id = session.get('user_id')
    admin_username = session.get('username')

    c.execute("SELECT * FROM payment_transactions WHERE id = ?", (payment_id,))
    pay = c.fetchone()
    if not pay:
        flash("Transaction not found.", "error")
        return redirect(url_for('admin_payments'))

    c.execute("UPDATE payment_transactions SET status = 'Rejected' WHERE id = ?", (payment_id,))
    db.commit()

    database.log_admin_action(
        admin_id=admin_id,
        admin_username=admin_username,
        action="REJECT_PAYMENT",
        target_type="payment",
        target_id=payment_id,
        details=f"Declined UPI Ref {pay['transaction_ref']} on test #{pay['paper_id']}.",
        ip_address=request.remote_addr,
        conn=db
    )

    flash(f"Transaction reference '{pay['transaction_ref']}' has been marked Rejected.", "info")
    return redirect(url_for('admin_payments'))

@app.route('/admin/settings')
@admin_required
def admin_settings():
    db = get_db()
    c = db.cursor()

    c.execute("SELECT key, value FROM site_settings")
    settings = {r['key']: r['value'] for r in c.fetchall()}

    c.execute("SELECT * FROM recruitment_update_logs ORDER BY id DESC LIMIT 5")
    update_logs = [dict(l) for l in c.fetchall()]

    return render_template('admin/settings.html', settings=settings, update_logs=update_logs)

@app.route('/admin/settings/update-payment', methods=['POST'])
@admin_required
def admin_settings_update_payment():
    price = request.form.get('mock_test_price', '5').strip()
    upi_id = request.form.get('upi_id', 'pm204664-1@okaxis').strip()
    upi_name = request.form.get('upi_name', 'Er. Prashant Mishra').strip()

    database.set_setting('mock_test_price', price, "Standard cost in INR per paid mock test attempt")
    database.set_setting('upi_id', upi_id, "Active UPI ID for student payments")
    database.set_setting('upi_name', upi_name, "Payee display name for UPI transactions")

    qr_file = request.files.get('upi_qr_file')
    if qr_file and qr_file.filename:
        filename = secure_filename(f"upi_qr_{int(time.time())}_{qr_file.filename}")
        save_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'payment')
        os.makedirs(save_dir, exist_ok=True)
        dest_path = os.path.join(save_dir, filename)
        qr_file.save(dest_path)
        database.set_setting('upi_qr_image', f"/static/uploads/payment/{filename}")

    admin_id = session.get('user_id')
    admin_username = session.get('username')
    database.log_admin_action(
        admin_id=admin_id,
        admin_username=admin_username,
        action="UPDATE_PAYMENT_SETTINGS",
        target_type="settings",
        details=f"Updated test price to ₹{price}, UPI ID to {upi_id}.",
        ip_address=request.remote_addr
    )

    flash("Payment settings and UPI configuration updated successfully.", "success")
    return redirect(url_for('admin_settings'))

@app.route('/admin/settings/update-announcement', methods=['POST'])
@admin_required
def admin_settings_update_announcement():
    msg = request.form.get('site_announcement', '').strip()
    database.set_setting('site_announcement', msg)

    admin_id = session.get('user_id')
    admin_username = session.get('username')
    database.log_admin_action(
        admin_id=admin_id,
        admin_username=admin_username,
        action="UPDATE_ANNOUNCEMENT",
        target_type="settings",
        details=f"Broadcast updated: {msg[:40]}...",
        ip_address=request.remote_addr
    )

    flash("Broadcast announcement ticker updated.", "success")
    return redirect(url_for('admin_settings'))

@app.route('/admin/recruitment/sync-now', methods=['POST'])
@admin_required
def admin_recruitment_sync_now():
    res = recruitment_updater.check_recruitment_updates(manual=True)
    admin_id = session.get('user_id')
    admin_username = session.get('username')
    database.log_admin_action(
        admin_id=admin_id,
        admin_username=admin_username,
        action="SYNC_RECRUITMENTS",
        target_type="recruitment",
        details=f"Manual sync triggered: {res['items_updated']} items updated. {res['details']}",
        ip_address=request.remote_addr
    )
    flash(f"Recruitment Sync Result ({res['status']}): {res['details']}", "success" if res['status'] == 'Success' else "warning")
    return redirect(request.referrer or url_for('admin_settings'))

@app.route('/admin/exams')
@admin_required
def admin_exams():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM defence_exams ORDER BY id ASC")
    exams = [dict(e) for e in c.fetchall()]
    return render_template('admin/exams.html', exams=exams)

@app.route('/admin/exams/add', methods=['POST'])
@admin_required
def admin_add_exam():
    code = request.form.get('code', '').strip().upper()
    name = request.form.get('name', '').strip()
    organization = request.form.get('organization', '').strip()
    category = request.form.get('category', 'Tri-Services')
    min_age = float(request.form.get('min_age', 17.5))
    max_age = float(request.form.get('max_age', 21.0))
    educational_qualification = request.form.get('educational_qualification', '').strip()
    official_portal_url = request.form.get('official_portal_url', '').strip()
    description = request.form.get('description', '').strip()

    db = get_db()
    c = db.cursor()
    try:
        c.execute('''
        INSERT INTO defence_exams (
            code, name, organization, category, description, eligibility_summary,
            min_age, max_age, educational_qualification, official_portal_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, organization, category, description, educational_qualification,
              min_age, max_age, educational_qualification, official_portal_url))
        db.commit()
        admin_id = session.get('user_id')
        admin_username = session.get('username')
        database.log_admin_action(admin_id, admin_username, "ADD_EXAM", "exam", code, f"Created {name}", request.remote_addr)
        flash(f"Examination '{name} ({code})' added successfully.", "success")
    except sqlite3.IntegrityError:
        flash(f"Exam code '{code}' already exists.", "error")

    return redirect(url_for('admin_exams'))

@app.route('/admin/syllabus')
@admin_required
def admin_syllabus():
    db = get_db()
    c = db.cursor()
    selected_exam = request.args.get('exam', '').strip()

    sql = "SELECT * FROM exam_syllabus"
    params = []
    if selected_exam:
        sql += " WHERE exam_code = ?"
        params.append(selected_exam)
    sql += " ORDER BY exam_code ASC, id ASC"

    c.execute(sql, params)
    syllabus_items = [dict(s) for s in c.fetchall()]

    c.execute("SELECT DISTINCT exam_code FROM exam_syllabus ORDER BY exam_code ASC")
    exam_codes = [r[0] for r in c.fetchall()]

    return render_template(
        'admin/syllabus.html',
        syllabus_items=syllabus_items,
        exam_codes=exam_codes,
        selected_exam=selected_exam
    )

@app.route('/admin/syllabus/add', methods=['POST'])
@admin_required
def admin_add_syllabus():
    exam_code = request.form.get('exam_code', '').strip().upper()
    stage_name = request.form.get('stage_name', '').strip()
    subject = request.form.get('subject', '').strip()
    topic_name = request.form.get('topic_name', '').strip()
    subtopics = request.form.get('subtopics', '').strip()
    question_count = int(request.form.get('question_count', 0))
    marks_per_question = float(request.form.get('marks_per_question', 1.0))
    negative_marks = float(request.form.get('negative_marks', 0.25))
    duration_minutes = int(request.form.get('duration_minutes', 60))
    official_source = request.form.get('official_source', '').strip()

    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO exam_syllabus (
        exam_code, stage_name, subject, topic_name, subtopics,
        question_count, marks_per_question, negative_marks, duration_minutes,
        official_source, last_verified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (exam_code, stage_name, subject, topic_name, subtopics,
          question_count, marks_per_question, negative_marks, duration_minutes,
          official_source, datetime.now().strftime("%d-%b-%Y")))
    db.commit()

    admin_id = session.get('user_id')
    admin_username = session.get('username')
    database.log_admin_action(admin_id, admin_username, "ADD_SYLLABUS", "syllabus", exam_code, f"Added topic '{topic_name}'", request.remote_addr)

    flash("Syllabus topic added successfully.", "success")
    return redirect(url_for('admin_syllabus', exam=exam_code))

@app.route('/admin/syllabus/delete/<int:item_id>', methods=['POST'])
@admin_required
def admin_delete_syllabus(item_id):
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM exam_syllabus WHERE id = ?", (item_id,))
    db.commit()
    flash("Syllabus topic deleted.", "info")
    return redirect(url_for('admin_syllabus'))

@app.route('/admin/questions/import')
@admin_required
def admin_questions_import_view():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, title, exam_code, subject FROM test_papers ORDER BY title ASC")
    papers = [dict(p) for p in c.fetchall()]
    return render_template('admin/question_import.html', papers=papers)

@app.route('/admin/questions/import-file', methods=['POST'])
@admin_required
def admin_questions_import_file():
    paper_id = request.form.get('paper_id')
    import_file = request.files.get('import_file')

    if not paper_id or not import_file or not import_file.filename:
        flash("Please select both a target test paper and a valid CSV or JSON file.", "error")
        return redirect(url_for('admin_questions_import_view'))

    db = get_db()
    c = db.cursor()
    c.execute("SELECT exam_code, subject FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Target test paper not found.", "error")
        return redirect(url_for('admin_questions_import_view'))

    exam_code = p_row['exam_code']
    default_subject = p_row['subject']

    raw_bytes = import_file.read()
    filename = import_file.filename.lower()

    imported_count = 0
    duplicate_count = 0

    try:
        rows_to_insert = []
        if filename.endswith('.json'):
            data = json.loads(raw_bytes.decode('utf-8'))
            if isinstance(data, dict):
                data = data.get('questions', [])
            for item in data:
                rows_to_insert.append(item)
        elif filename.endswith('.csv'):
            csv_text = raw_bytes.decode('utf-8-sig', errors='replace')
            reader = csv.DictReader(io.StringIO(csv_text))
            for row in reader:
                rows_to_insert.append(row)
        else:
            flash("Unsupported file format. Please upload a .json or .csv file.", "error")
            return redirect(url_for('admin_questions_import_view'))

        for r in rows_to_insert:
            q_text_en = (r.get('question_text_en') or r.get('question') or '').strip()
            if not q_text_en:
                continue

            # Duplicate check
            c.execute("SELECT id FROM questions WHERE paper_id = ? AND question_text_en = ?", (paper_id, q_text_en))
            if c.fetchone():
                duplicate_count += 1
                continue

            subject = (r.get('subject') or default_subject).strip()
            topic = (r.get('topic') or 'General').strip()
            q_text_hi = (r.get('question_text_hi') or '').strip()
            opt_a = (r.get('option_a_en') or r.get('option_a') or '').strip()
            opt_b = (r.get('option_b_en') or r.get('option_b') or '').strip()
            opt_c = (r.get('option_c_en') or r.get('option_c') or '').strip()
            opt_d = (r.get('option_d_en') or r.get('option_d') or '').strip()
            correct = (r.get('correct_option') or r.get('answer') or 'A').strip().upper()
            expl = (r.get('explanation_en') or r.get('explanation') or 'Step-by-step solution verified.').strip()
            diff = (r.get('difficulty') or 'Moderate').strip()

            c.execute('''
            INSERT INTO questions (
                paper_id, exam_code, subject, topic, difficulty,
                question_text_en, question_text_hi,
                option_a_en, option_a_hi,
                option_b_en, option_b_hi,
                option_c_en, option_c_hi,
                option_d_en, option_d_hi,
                correct_option, explanation_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                paper_id, exam_code, subject, topic, diff,
                q_text_en, q_text_hi,
                opt_a, opt_a,
                opt_b, opt_b,
                opt_c, opt_c,
                opt_d, opt_d,
                correct, expl
            ))
            imported_count += 1

        db.commit()

        # Update paper's total_questions count
        c.execute("SELECT COUNT(*) FROM questions WHERE paper_id = ?", (paper_id,))
        new_q_count = c.fetchone()[0]
        c.execute("UPDATE test_papers SET total_questions = ? WHERE id = ?", (new_q_count, paper_id))
        db.commit()

        admin_id = session.get('user_id')
        admin_username = session.get('username')
        database.log_admin_action(
            admin_id, admin_username, "IMPORT_QUESTIONS", "paper", paper_id,
            f"Imported {imported_count} questions ({duplicate_count} skipped duplicates)",
            request.remote_addr
        )

        flash(f"Successfully imported {imported_count} questions into Paper #{paper_id}. ({duplicate_count} duplicates skipped)", "success")
        return redirect(url_for('admin_pyqs'))

    except Exception as e:
        flash(f"Error parsing import file: {str(e)}", "error")
        return redirect(url_for('admin_questions_import_view'))

@app.route('/admin/audit-logs')
@admin_required
def admin_audit_logs_view():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT 100")
    logs = [dict(l) for l in c.fetchall()]
    return render_template('admin/audit_logs.html', logs=logs)


if __name__ == '__main__':
    print("=" * 60)
    print("  DEFENCE PATH - FULL-STACK ARMED FORCES PORTAL")
    print("  'Your Dream. Your Discipline. Your Uniform.'")
    print("  Project Developer: Er. Prashant Mishra (Ph: 6390314464)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)

import os
import json
import sqlite3
import time
import re
from collections import defaultdict
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, session,
    flash, jsonify, send_file, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

import database
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

# Initialize database if not exists
if not os.path.exists(database.DB_PATH):
    database.init_db()
    database.seed_data()

def get_db():
    if 'db' not in g:
        g.db = database.get_db()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Context processor to inject dynamic developer profile and live stats everywhere
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
    return dict(dev=dev)

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
    return render_template('tests.html', mock_tests=mock_tests)


# ==========================================
# CBT ENGINE & TEST SUBMISSION API
# ==========================================

@app.route('/start-test/<int:paper_id>')
@app.route('/test-cbt/<int:paper_id>')
def start_test(paper_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM test_papers WHERE id = ?", (paper_id,))
    p_row = c.fetchone()
    if not p_row:
        flash("Examination paper not found.", "warning")
        return redirect(url_for('tests_view'))

    paper = dict(p_row)

    # Fetch associated questions
    c.execute("SELECT * FROM questions WHERE paper_id = ? ORDER BY id ASC", (paper_id,))
    q_rows = c.fetchall()

    if not q_rows:
        # Fallback: fetch questions for this exam_code
        c.execute("SELECT * FROM questions WHERE exam_code = ? ORDER BY id ASC", (paper['exam_code'],))
        q_rows = c.fetchall()

    questions = [dict(q) for q in q_rows]

    return render_template(
        'test_cbt.html',
        paper=paper,
        paper_json=json.dumps(paper),
        questions_json=json.dumps(questions)
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

    # User binding: if logged in, save to user; otherwise save to demo student account
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
    db.commit()
    attempt_id = c.lastrowid

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

        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE (username = ? OR email = ?) AND role = 'admin'", (identifier, identifier))
        admin_row = c.fetchone()

        if admin_row and check_password_hash(admin_row['password_hash'], password):
            clear_failed_attempts(f"admin_{client_ip}")
            clear_failed_attempts(f"admin_{identifier}")
            
            session.clear()
            session['user_id'] = admin_row['id']
            session['username'] = admin_row['username']
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


if __name__ == '__main__':
    print("=" * 60)
    print("  DEFENCE PATH - FULL-STACK ARMED FORCES PORTAL")
    print("  'Your Dream. Your Discipline. Your Uniform.'")
    print("  Project Developer: Er. Prashant Mishra (Ph: 6390314464)")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)

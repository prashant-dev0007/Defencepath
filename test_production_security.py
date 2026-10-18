import unittest
import os
import json
from app import app
import database

class TestProductionSecurity(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        # Ensure database is initialised
        if not os.path.exists(database.DB_PATH):
            database.init_db()
            database.seed_data()

    # 1. Verify Public Frontend has NO PPT links or demo badges
    def test_public_pages_no_ppt_exposure(self):
        pages_to_check = ['/', '/jobs', '/portals', '/eligibility', '/pyq', '/tests', '/about', '/contact', '/login']
        for page in pages_to_check:
            res = self.client.get(page)
            self.assertEqual(res.status_code, 200, f"Page {page} failed to load")
            html = res.data.decode('utf-8')
            self.assertNotIn('href="/presentation"', html, f"Page {page} exposes /presentation link")
            self.assertNotIn('href="/download-presentation-pptx"', html, f"Page {page} exposes /download-presentation-pptx link")
            self.assertNotIn('Project PPT', html, f"Page {page} exposes 'Project PPT' label")
            self.assertNotIn('quick-demo-login', html, f"Page {page} exposes demo login links")
            self.assertNotIn('badge-demo', html, f"Page {page} exposes badge-demo")
        print("[PASS] Public pages do not expose PPT, demo badges, or demo login links.")

    # 2. Verify PPT and Demo Login Endpoints are completely DELETED (Return 404)
    def test_ppt_and_demo_endpoints_deleted(self):
        deleted_endpoints = ['/presentation', '/download-presentation-pptx', '/quick-demo-login']
        for ep in deleted_endpoints:
            res = self.client.get(ep, follow_redirects=False)
            self.assertEqual(res.status_code, 404, f"Endpoint {ep} should be deleted and return 404")
        print("[PASS] PPT and 1-click demo endpoints are completely deleted (404 Not Found).")

    # 3. Verify Ordinary Student is BLOCKED from Admin and other student's data (IDOR)
    def test_student_blocked_from_admin_and_idor(self):
        # Login as student
        res_login = self.client.post('/login', data={
            'username': 'aspirant',
            'password': 'aspirant123'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)

        # Attempt to access /admin
        res_admin = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn('/', res_admin.headers.get('Location'))

        # Attempt to access /admin/student-results
        res_admin_results = self.client.get('/admin/student-results', follow_redirects=False)
        self.assertEqual(res_admin_results.status_code, 302)

        # IDOR Test: Student with ID 2 trying to view attempt owned by student with ID 1
        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT id, user_id FROM test_attempts ORDER BY id ASC LIMIT 5")
        attempts = c.fetchall()
        for att in attempts:
            att_id = att['id']
            owner_id = att['user_id']
            with self.client.session_transaction() as sess:
                current_id = sess.get('user_id')
            if owner_id != current_id:
                idor_res = self.client.get(f'/test-result/{att_id}', follow_redirects=False)
                self.assertEqual(idor_res.status_code, 302, f"IDOR vulnerability on /test-result/{att_id}")
                self.assertIn('/dashboard', idor_res.headers.get('Location'))
                break

        print("[PASS] Ordinary student blocked from admin console and other students' data (IDOR protected).")

    # 4. Verify Administrator CAN access Admin and Student Results
    def test_administrator_full_access(self):
        # Login as admin via /admin/login
        res_admin_login = self.client.post('/admin/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(res_admin_login.status_code, 200)

        # Access /admin
        res_admin = self.client.get('/admin')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"Admin Command Centre", res_admin.data)
        self.assertIn(b"Student Results", res_admin.data)

        # Access /admin/student-results
        res_results = self.client.get('/admin/student-results')
        self.assertEqual(res_results.status_code, 200)
        self.assertIn(b"Student Results & Test Records", res_results.data)

        print("[PASS] Administrator verified with authorized access to admin dashboard and student results.")

    # 5. Verify Registration Security & Input Validation
    def test_registration_security(self):
        # Public registration cannot escalate role
        res_reg = self.client.post('/register', data={
            'full_name': 'Test New Cadet',
            'username': 'newcadet123',
            'email': 'newcadet@example.com',
            'password': 'secretpassword123',
            'confirm_password': 'secretpassword123',
            'role': 'admin' # Try privilege escalation
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)

        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT role FROM users WHERE username = 'newcadet123'")
        row = c.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['role'], 'student', "Role must strictly be forced to 'student'!")

        # Short password rejected
        res_short = self.client.post('/register', data={
            'full_name': 'Short Pass',
            'username': 'shortpassuser',
            'email': 'short@example.com',
            'password': '123',
            'confirm_password': '123'
        }, follow_redirects=True)
        c.execute("SELECT id FROM users WHERE username = 'shortpassuser'")
        self.assertIsNone(c.fetchone(), "Short passwords must be rejected!")

        print("[PASS] Registration enforces strict validation and role restriction.")

    # 6. Verify Mock Tests, PYQs, and Questions Integrity
    def test_educational_content_integrity(self):
        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM questions")
        total_q = c.fetchone()[0]
        self.assertGreater(total_q, 10, "Questions bank must remain intact!")

        c.execute("SELECT COUNT(*) FROM test_papers")
        total_papers = c.fetchone()[0]
        self.assertGreater(total_papers, 3, "Test papers must remain intact!")

        # Check that tests list and test CBT simulator load
        res_tests = self.client.get('/tests')
        self.assertEqual(res_tests.status_code, 200)

        c.execute("SELECT id FROM test_papers LIMIT 1")
        pid = c.fetchone()[0]
        res_cbt = self.client.get(f'/test-cbt/{pid}')
        self.assertEqual(res_cbt.status_code, 200)

        print(f"[PASS] Educational integrity confirmed: {total_papers} test papers, {total_q} questions fully intact.")

if __name__ == '__main__':
    unittest.main()

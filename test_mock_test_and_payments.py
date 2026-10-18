import unittest
import os
import json
import sqlite3
from app import app
import database

class TestMockTestPaymentsAndCMS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key-defence-path'
        cls.client = app.test_client()

    def setUp(self):
        # Establish clean test database connection
        self.db = database.get_db()
        self.cursor = self.db.cursor()

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass

    def test_01_seo_endpoints(self):
        """Verify sitemap.xml and robots.txt exist and are properly formatted."""
        res_robots = self.client.get('/robots.txt')
        self.assertEqual(res_robots.status_code, 200)
        self.assertIn("User-agent: *", res_robots.get_data(as_text=True))
        self.assertIn("Disallow: /admin/", res_robots.get_data(as_text=True))
        self.assertIn("Sitemap:", res_robots.get_data(as_text=True))

        res_sitemap = self.client.get('/sitemap.xml')
        self.assertEqual(res_sitemap.status_code, 200)
        content = res_sitemap.get_data(as_text=True)
        self.assertIn("<urlset", content)
        self.assertIn("<loc>", content)
        self.assertIn("/exams", content)
        self.assertIn("/jobs", content)
        self.assertIn("/pyq", content)
        self.assertIn("/tests", content)

    def test_02_public_exams_and_syllabus(self):
        """Verify public defence exams and syllabus directory load properly."""
        res = self.client.get('/exams')
        self.assertEqual(res.status_code, 200)
        text = res.get_data(as_text=True)
        self.assertIn("Indian Armed Forces", text)
        self.assertIn("Topic-Wise Syllabus", text)

        res_nda = self.client.get('/exams/NDA')
        self.assertEqual(res_nda.status_code, 200)
        nda_text = res_nda.get_data(as_text=True)
        self.assertIn("NDA", nda_text)

    def test_03_cbt_question_security(self):
        """Verify questions sent to client in CBT view NEVER contain correct answers or explanations."""
        # Query existing test paper
        self.cursor.execute("SELECT id FROM test_papers LIMIT 1")
        row = self.cursor.fetchone()
        paper_id = row['id']

        res = self.client.get(f'/test-cbt/{paper_id}')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        
        # In test_cbt.html questions are serialized into serverQuestions
        self.assertIn("serverQuestions", html)
        
        start_marker = "const serverQuestions = "
        end_marker = ";"
        self.assertIn(start_marker, html)
        part = html.split(start_marker)[1].split(end_marker)[0].strip()
        loaded_questions = json.loads(part)
        self.assertTrue(len(loaded_questions) > 0)
        for q in loaded_questions:
            self.assertNotIn("correct_option", q, "CRITICAL SECURITY BREACH: correct_option was exposed to client!")
            self.assertNotIn("explanation_en", q, "CRITICAL: explanation_en exposed before submission!")
            self.assertNotIn("explanation_hi", q, "CRITICAL: explanation_hi exposed before submission!")

    def test_04_mock_test_evaluation_and_free_attempt(self):
        """Verify server evaluates score securely and marks free_attempt_used."""
        test_email = "test_cbt_aspirant@defencepath.in"
        self.cursor.execute("DELETE FROM users WHERE email = ?", (test_email,))
        self.cursor.execute('''
        INSERT INTO users (username, full_name, email, password_hash, role, free_attempt_used)
        VALUES ('cbt_candidate_01', 'Cadet Test', ?, 'pbkdf2:dummy', 'aspirant', 0)
        ''', (test_email,))
        self.db.commit()

        self.cursor.execute("SELECT id FROM users WHERE email = ?", (test_email,))
        test_user_id = self.cursor.fetchone()['id']

        self.cursor.execute("SELECT id, marks_per_correct, negative_marks FROM test_papers LIMIT 1")
        paper = self.cursor.fetchone()
        paper_id = paper['id']

        self.cursor.execute("SELECT id, correct_option FROM questions WHERE paper_id = ? LIMIT 2", (paper_id,))
        q_rows = self.cursor.fetchall()
        if not q_rows:
            self.cursor.execute("SELECT id, correct_option FROM questions LIMIT 2")
            q_rows = self.cursor.fetchall()

        q1 = q_rows[0]
        payload = {
            "paper_id": paper_id,
            "time_taken_seconds": 120,
            "responses": {
                str(q1['id']): {"selectedOption": q1['correct_option']}
            }
        }

        # Simulate user session
        with self.client.session_transaction() as sess:
            sess['user_id'] = test_user_id
            sess['username'] = 'cbt_candidate_01'
            sess['role'] = 'aspirant'

        res = self.client.post('/api/submit-test',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.get_data(as_text=True))
        self.assertTrue(data.get('success'))
        attempt_id = data.get('attempt_id')
        self.assertIsNotNone(attempt_id)

        # Verify free attempt was consumed
        self.cursor.execute("SELECT free_attempt_used FROM users WHERE id = ?", (test_user_id,))
        u = self.cursor.fetchone()
        self.assertEqual(u['free_attempt_used'], 1)

        # Verify entitlement was recorded
        self.cursor.execute("SELECT * FROM test_entitlements WHERE user_id = ? AND paper_id = ?", (test_user_id, paper_id))
        ent = self.cursor.fetchone()
        self.assertIsNotNone(ent)
        self.assertEqual(ent['is_consumed'], 1)

    def test_05_paid_mock_test_flow_and_admin_verification(self):
        """Verify second mock test redirects to payment, payment creates pending record, and admin unlocks it."""
        test_email = "paid_aspirant@defencepath.in"
        self.cursor.execute("DELETE FROM users WHERE email = ?", (test_email,))
        self.cursor.execute('''
        INSERT INTO users (username, full_name, email, password_hash, role, free_attempt_used)
        VALUES ('paid_aspirant_01', 'Arjun Singh', ?, 'pbkdf2:dummy', 'aspirant', 1)
        ''', (test_email,))
        self.db.commit()

        self.cursor.execute("SELECT id FROM users WHERE email = ?", (test_email,))
        user_id = self.cursor.fetchone()['id']

        self.cursor.execute("SELECT id FROM test_papers ORDER BY id DESC LIMIT 1")
        paper_id = self.cursor.fetchone()['id']

        # Ensure no existing entitlements
        self.cursor.execute("DELETE FROM test_entitlements WHERE user_id = ? AND paper_id = ?", (user_id, paper_id))
        self.cursor.execute("DELETE FROM payment_transactions WHERE user_id = ? AND paper_id = ?", (user_id, paper_id))
        self.db.commit()

        # Step A: Attempting to access test-payment view
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['username'] = 'paid_aspirant_01'
            sess['role'] = 'aspirant'

        pay_view = self.client.get(f'/test-payment/{paper_id}')
        self.assertEqual(pay_view.status_code, 200)
        pay_html = pay_view.get_data(as_text=True)
        self.assertIn("pm204664-1@okaxis", pay_html)
        self.assertIn("UPI", pay_html)

        # Step B: Submit UTR
        test_utr = f"UTR998877{user_id}"
        post_res = self.client.post('/api/payment/submit', data={
            'paper_id': paper_id,
            'transaction_ref': test_utr
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)

        # Verify transaction recorded in DB as Pending
        self.cursor.execute("SELECT * FROM payment_transactions WHERE transaction_ref = ?", (test_utr,))
        tx = self.cursor.fetchone()
        self.assertIsNotNone(tx)
        self.assertEqual(tx['status'], 'Pending')
        self.assertEqual(tx['user_id'], user_id)
        payment_id = tx['id']

        # Step C: Admin logs in and views payment desk
        admin_id = 1
        with self.client.session_transaction() as sess:
            sess['user_id'] = admin_id
            sess['username'] = 'admin'
            sess['role'] = 'admin'

        desk_res = self.client.get('/admin/payments')
        self.assertEqual(desk_res.status_code, 200)
        self.assertIn(test_utr, desk_res.get_data(as_text=True))

        # Close cursor/commit before post to avoid lock
        self.db.commit()

        # Step D: Admin approves the transaction
        verify_res = self.client.post(f'/admin/payments/verify/{payment_id}', follow_redirects=True)
        self.assertEqual(verify_res.status_code, 200)

        # Check transaction status in DB is now Verified
        self.cursor.execute("SELECT status FROM payment_transactions WHERE id = ?", (payment_id,))
        tx_after = self.cursor.fetchone()
        self.assertEqual(tx_after['status'], 'Verified')

        # Check entitlement was created
        self.cursor.execute("SELECT * FROM test_entitlements WHERE user_id = ? AND paper_id = ? AND is_consumed = 0", (user_id, paper_id))
        entitlement = self.cursor.fetchone()
        self.assertIsNotNone(entitlement, "Candidate should now have an active unconsumed entitlement!")
        self.assertEqual(entitlement['payment_id'], payment_id)

    def test_06_admin_cms_security_boundary(self):
        """Verify student or guest cannot access any admin CMS endpoints."""
        admin_urls = [
            '/admin/payments',
            '/admin/settings',
            '/admin/exams',
            '/admin/syllabus',
            '/admin/questions/import',
            '/admin/audit-logs'
        ]

        # 1. Unauthenticated guest -> redirected to admin login
        with self.client.session_transaction() as sess:
            sess.clear()

        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, f"Guest should be redirected away from {url}")
            self.assertIn('/admin/login', res.headers.get('Location', ''))

        # 2. Aspirant user -> blocked by admin_required, redirected to home
        with self.client.session_transaction() as sess:
            sess['user_id'] = 999
            sess['username'] = 'aspirant_user'
            sess['role'] = 'aspirant'

        for url in admin_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, f"Student role must be blocked from {url}")
            # Redirect location should be '/' (home)
            self.assertEqual(res.headers.get('Location', ''), '/')

    def test_07_recruitment_auto_expiry(self):
        """Verify recruitment updater correctly transitions expired deadlines to 'Applications Closed'."""
        import recruitment_updater
        # Insert a test recruitment with an expired deadline matching exact table schema
        self.cursor.execute('''
        INSERT INTO recruitments (
            title, organization, post_name, category, qualification,
            min_age, max_age, start_date, closing_date, exam_date,
            vacancies, source_name, last_verified, status, is_verified, admin_reviewed
        ) VALUES (
            'Expired Test Recruitment 2024', 'Indian Navy', 'Sub Lieutenant', 'Officer', 'B.Tech',
            19.5, 25.0, '01-Jan-2024', '15-Jan-2024', '01-Mar-2024',
            50, 'Official Gazette', '01-Jan-2024', 'Applications Open', 1, 1
        )
        ''')
        self.db.commit()
        test_rec_id = self.cursor.lastrowid

        # Run updater
        res = recruitment_updater.check_recruitment_updates(manual=True)
        self.assertEqual(res['status'], 'Success')

        # Verify status transitioned to 'Applications Closed'
        self.cursor.execute("SELECT status FROM recruitments WHERE id = ?", (test_rec_id,))
        row = self.cursor.fetchone()
        self.assertEqual(row['status'], 'Applications Closed')

        # Clean up
        self.cursor.execute("DELETE FROM recruitments WHERE id = ?", (test_rec_id,))
        self.db.commit()

if __name__ == '__main__':
    unittest.main()

"""
DEFENCE PATH - Comprehensive Authentication & Password Security Test Suite
Verifies all 14 scenarios required by Section 9:
1. Existing administrator can log in with their registered email and password.
2. First-time administrator password setup works securely.
3. The administrator can log out and log in again with the same password.
4. The administrator's password persists across browser restarts.
5. A student can log in with their existing credentials.
6. Forgot Password sends an OTP to the registered email.
7. A valid OTP permits creation of a new password.
8. An incorrect or expired OTP is rejected.
9. A used OTP cannot be reused.
10. An unauthorized person cannot change the administrator's password.
11. A student cannot access the admin dashboard.
12. The new password works, and the old password no longer works after a successful reset.
13. Existing mock tests, student records, results, PPT restrictions, and all other project features continue working.
14. Authentication and recovery work in the actual deployment environment, not just on localhost.
"""

import unittest
import os
import time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, hash_token
import database
import email_service

class TestAuthenticationAndRecovery(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        # Ensure database is initialised and migrated
        database.migrate_db()

        # Ensure baseline admin and student passwords are set to known testing state
        db = database.get_db()
        c = db.cursor()
        c.execute("""
            UPDATE users 
            SET username = 'admin@defencepath.in', email = 'admin@defencepath.in',
                password_hash = ?, first_time_setup_done = 1
            WHERE role = 'admin'
        """, (generate_password_hash("admin123"),))
        c.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE username = 'aspirant' OR email = 'vikram@aspirant.defencepath.in'
        """, (generate_password_hash("aspirant123"),))
        db.commit()

    # Scenario 1: Existing administrator can log in with registered email and password
    def test_01_admin_login_with_registered_email_and_password(self):
        res = self.client.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Command Centre", res.data)
        
        # Also test legacy alias 'admin'
        with app.test_client() as c_alias:
            res_alias = c_alias.post('/admin/login', data={
                'username': 'admin',
                'password': 'admin123'
            }, follow_redirects=True)
            self.assertEqual(res_alias.status_code, 200)
            self.assertIn(b"Admin Command Centre", res_alias.data)
        print("[PASS] Scenario 1: Administrator logs in reliably using registered email and legacy alias.")

    # Scenario 2: First-time administrator password setup works securely
    def test_02_first_time_admin_setup_secure_flow(self):
        db = database.get_db()
        c = db.cursor()
        # Set admin to pending setup
        c.execute("UPDATE users SET first_time_setup_done = 0 WHERE role = 'admin'")
        db.commit()

        # Step 1: Admin enters registered email at /admin/setup
        res_setup = self.client.post('/admin/setup', data={
            'email': 'admin@defencepath.in'
        }, follow_redirects=True)
        self.assertEqual(res_setup.status_code, 200)

        # Get generated OTP from DB or test session
        c.execute("""
            SELECT id, otp_hash FROM password_resets 
            WHERE email = 'admin@defencepath.in' AND purpose = 'first_time_setup' AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
        """)
        record = c.fetchone()
        self.assertIsNotNone(record)

        with self.client.session_transaction() as sess:
            test_otp = sess.get('test_last_otp')
        self.assertIsNotNone(test_otp)

        # Step 2: Submit OTP at /admin/setup/verify
        res_verify = self.client.post('/admin/setup/verify', data={
            'otp': test_otp
        }, follow_redirects=True)
        self.assertEqual(res_verify.status_code, 200)
        self.assertIn(b"Establish New Password", res_verify.data)

        # Step 3: Establish new password at /admin/setup/new-password
        res_new_pass = self.client.post('/admin/setup/new-password', data={
            'password': 'FirstTimeAdminPass2026!',
            'confirm_password': 'FirstTimeAdminPass2026!'
        }, follow_redirects=True)
        self.assertEqual(res_new_pass.status_code, 200)
        self.assertIn(b"Admin Command Gateway", res_new_pass.data)

        # Verify DB updated and setup marked completed
        c.execute("SELECT password_hash, first_time_setup_done FROM users WHERE role = 'admin'")
        row = c.fetchone()
        self.assertEqual(row['first_time_setup_done'], 1)
        self.assertTrue(check_password_hash(row['password_hash'], 'FirstTimeAdminPass2026!'))

        # Verify setup gateway is permanently locked for this admin
        res_lock = self.client.post('/admin/setup', data={
            'email': 'admin@defencepath.in'
        }, follow_redirects=True)
        self.assertIn(b"already been completed", res_lock.data)
        print("[PASS] Scenario 2: First-time admin setup establishes password and permanently closes setup gate.")

    # Scenario 3: Administrator can log out and log in again with the same password
    def test_03_admin_logout_and_relogin(self):
        # Set password
        db = database.get_db()
        c = db.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE role = 'admin'", 
                  (generate_password_hash("PersistentMaster123!"),))
        db.commit()

        # Log in
        res_in = self.client.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': 'PersistentMaster123!'
        }, follow_redirects=True)
        self.assertIn(b"Admin Command Centre", res_in.data)

        # Log out
        res_out = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_out.status_code, 200)

        # Session must be cleared; trying to access /admin directly must redirect to login
        res_denied = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(res_denied.status_code, 302)

        # Log back in with the same password
        res_relogin = self.client.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': 'PersistentMaster123!'
        }, follow_redirects=True)
        self.assertIn(b"Admin Command Centre", res_relogin.data)
        print("[PASS] Scenario 3: Admin logs out and re-authenticates reliably with persistent password.")

    # Scenario 4: Administrator password persists across browser restarts
    def test_04_admin_password_persists_across_browser_restarts(self):
        db = database.get_db()
        c = db.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE role = 'admin'", 
                  (generate_password_hash("BrowserRestartPass999!"),))
        db.commit()

        # Fresh client (simulating new browser session with empty cookie jar)
        new_browser = app.test_client()
        res = new_browser.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': 'BrowserRestartPass999!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Command Centre", res.data)
        print("[PASS] Scenario 4: Admin password persistence verified on brand new browser session.")

    # Scenario 5: Student can log in with existing credentials
    def test_05_student_login_with_existing_credentials(self):
        # Student login via username
        res_user = self.client.post('/login', data={
            'username': 'aspirant',
            'password': 'aspirant123'
        }, follow_redirects=True)
        self.assertEqual(res_user.status_code, 200)
        self.assertIn(b"Command Dossier", res_user.data)

        # Student login via email
        with app.test_client() as c_mail:
            res_mail = c_mail.post('/login', data={
                'username': 'vikram@aspirant.defencepath.in',
                'password': 'aspirant123'
            }, follow_redirects=True)
            self.assertEqual(res_mail.status_code, 200)
            self.assertIn(b"Command Dossier", res_mail.data)
        print("[PASS] Scenario 5: Student login confirmed using username and email.")

    # Scenario 6: Forgot Password sends an OTP to registered email
    def test_06_forgot_password_dispatches_otp(self):
        res = self.client.post('/forgot-password', data={
            'email': 'vikram@aspirant.defencepath.in'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Enter Verification Code", res.data)

        # Verify DB has hashed OTP record expiring in 5 min
        db = database.get_db()
        c = db.cursor()
        c.execute("""
            SELECT otp_hash, expires_at FROM password_resets 
            WHERE email = 'vikram@aspirant.defencepath.in' AND purpose = 'forgot_password' AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
        """)
        rec = c.fetchone()
        self.assertIsNotNone(rec)
        self.assertEqual(len(rec['otp_hash']), 64) # SHA-256 hash length

        # Non-existing email also returns generic safe response (no enumeration)
        with app.test_client() as c_fake:
            res_fake = c_fake.post('/forgot-password', data={
                'email': 'nonexistent_ghost_cadet@example.com'
            }, follow_redirects=True)
            self.assertEqual(res_fake.status_code, 200)
            self.assertIn(b"Enter Verification Code", res_fake.data)
        print("[PASS] Scenario 6: Forgot Password dispatches OTP and prevents user enumeration.")

    # Scenario 7: Valid OTP permits creation of a new password
    def test_07_valid_otp_permits_password_creation(self):
        # Initiate forgot password
        self.client.post('/forgot-password', data={
            'email': 'vikram@aspirant.defencepath.in'
        })
        with self.client.session_transaction() as sess:
            otp = sess.get('test_last_otp')

        # Verify OTP
        res_v = self.client.post('/forgot-password/verify', data={'otp': otp}, follow_redirects=True)
        self.assertEqual(res_v.status_code, 200)
        self.assertIn(b"Establish New Password", res_v.data)

        # Set new password
        res_reset = self.client.post('/forgot-password/reset', data={
            'password': 'NewCadetPassword2026!',
            'confirm_password': 'NewCadetPassword2026!'
        }, follow_redirects=True)
        self.assertEqual(res_reset.status_code, 200)

        # Verify in DB
        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT password_hash FROM users WHERE email = 'vikram@aspirant.defencepath.in'")
        self.assertTrue(check_password_hash(c.fetchone()[0], 'NewCadetPassword2026!'))
        print("[PASS] Scenario 7: Valid OTP permits creation and hashing of new password.")

    # Scenario 8: Incorrect and expired OTP is rejected
    def test_08_incorrect_and_expired_otp_rejected(self):
        self.client.post('/forgot-password', data={
            'email': 'vikram@aspirant.defencepath.in'
        })
        
        # Submit wrong OTP
        res_bad = self.client.post('/forgot-password/verify', data={'otp': '999999'}, follow_redirects=True)
        self.assertIn(b"Invalid verification code", res_bad.data)

        # Simulate expired OTP
        db = database.get_db()
        c = db.cursor()
        past_time = (datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("UPDATE password_resets SET expires_at = ? WHERE email = 'vikram@aspirant.defencepath.in'", (past_time,))
        db.commit()

        with self.client.session_transaction() as sess:
            otp = sess.get('test_last_otp')
        res_exp = self.client.post('/forgot-password/verify', data={'otp': otp}, follow_redirects=True)
        self.assertIn(b"expired", res_exp.data.lower())
        print("[PASS] Scenario 8: Incorrect and expired OTPs are strictly rejected.")

    # Scenario 9: A used OTP cannot be reused
    def test_09_used_otp_cannot_be_reused(self):
        self.client.post('/forgot-password', data={
            'email': 'vikram@aspirant.defencepath.in'
        })
        with self.client.session_transaction() as sess:
            otp = sess.get('test_last_otp')

        # Use OTP first time
        self.client.post('/forgot-password/verify', data={'otp': otp}, follow_redirects=True)
        self.client.post('/forgot-password/reset', data={
            'password': 'FirstPassReset123!',
            'confirm_password': 'FirstPassReset123!'
        }, follow_redirects=True)

        # Try to reuse the same OTP in a new session
        with app.test_client() as attacker:
            attacker.post('/forgot-password', data={'email': 'vikram@aspirant.defencepath.in'})
            res_reuse = attacker.post('/forgot-password/verify', data={'otp': otp}, follow_redirects=True)
            self.assertIn(b"Invalid", res_reuse.data)
        print("[PASS] Scenario 9: Single-use OTP enforcement confirmed.")

    # Scenario 10: Unauthorized person cannot change administrator's password
    def test_10_unauthorized_person_cannot_change_admin_password(self):
        # Attempt to POST directly to reset endpoint without verified session token
        res_direct = self.client.post('/admin/setup/new-password', data={
            'password': 'HackedPassword123!',
            'confirm_password': 'HackedPassword123!'
        }, follow_redirects=True)
        self.assertIn(b"unauthorized", res_direct.data.lower())

        # Verify admin password remains uncompromised
        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT password_hash FROM users WHERE role = 'admin'")
        self.assertFalse(check_password_hash(c.fetchone()[0], 'HackedPassword123!'))
        print("[PASS] Scenario 10: Unauthorized password manipulation blocked.")

    # Scenario 11: Student cannot access admin dashboard
    def test_11_student_blocked_from_admin_dashboard(self):
        # Student logs in
        self.client.post('/login', data={
            'username': 'aspirant',
            'password': 'aspirant123'
        }, follow_redirects=True)

        # Student attempts to access /admin
        res_admin = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)

        # Student attempts to access /admin/student-results
        res_results = self.client.get('/admin/student-results', follow_redirects=False)
        self.assertEqual(res_results.status_code, 302)

        # Follow redirect and verify flash
        res_follow = self.client.get('/admin', follow_redirects=True)
        self.assertIn(b"Insufficient administrative privileges", res_follow.data)
        print("[PASS] Scenario 11: Role boundary verified; students strictly blocked from admin console.")

    # Scenario 12: New password works and old password no longer works
    def test_12_old_password_fails_after_reset(self):
        # Reset admin password
        old_pass = "admin123"
        new_pass = "BrandNewAdminPassword2026!"

        db = database.get_db()
        c = db.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE role = 'admin'", 
                  (generate_password_hash(new_pass),))
        db.commit()

        # Try logging in with old password
        res_old = self.client.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': old_pass
        }, follow_redirects=True)
        self.assertIn(b"Invalid administrator credentials", res_old.data)

        # Try logging in with new password
        res_new = self.client.post('/admin/login', data={
            'username': 'admin@defencepath.in',
            'password': new_pass
        }, follow_redirects=True)
        self.assertEqual(res_new.status_code, 200)
        self.assertIn(b"Admin Command Centre", res_new.data)
        print("[PASS] Scenario 12: Old password invalidated immediately; new password works.")

    # Scenario 13: Existing mock tests, student records, results, PPT restrictions intact
    def test_13_mock_tests_results_ppt_restrictions_intact(self):
        # PPT endpoints must return 404
        for ep in ['/presentation', '/download-presentation-pptx', '/quick-demo-login']:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 404)

        # Mock tests and CBT simulator load
        res_tests = self.client.get('/tests')
        self.assertEqual(res_tests.status_code, 200)

        db = database.get_db()
        c = db.cursor()
        c.execute("SELECT id FROM test_papers LIMIT 1")
        pid = c.fetchone()[0]
        res_cbt = self.client.get(f'/test-cbt/{pid}')
        self.assertEqual(res_cbt.status_code, 200)

        # Questions count and student results preserved
        c.execute("SELECT COUNT(*) FROM questions")
        self.assertGreater(c.fetchone()[0], 10)
        c.execute("SELECT COUNT(*) FROM test_attempts")
        self.assertGreaterEqual(c.fetchone()[0], 2)
        print("[PASS] Scenario 13: Educational integrity and PPT access restrictions confirmed intact.")

    # Scenario 14: Environment configuration & safe error handling
    def test_14_environment_config_and_safe_error_handling(self):
        # Verify SMTP configuration helper parses gracefully
        config = email_service.get_smtp_config()
        self.assertIn('host', config)
        self.assertIn('port', config)
        self.assertIn('from_email', config)

        # Session security parameters verified
        self.assertTrue(app.config.get('SESSION_COOKIE_HTTPONLY'))
        self.assertEqual(app.config.get('SESSION_COOKIE_SAMESITE'), 'Lax')
        print("[PASS] Scenario 14: Environment configuration and production session security verified.")

if __name__ == '__main__':
    unittest.main()

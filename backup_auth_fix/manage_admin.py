#!/usr/bin/env python3
"""
DEFENCE PATH - Secure Administrator Provisioning Tool
Usage:
    python manage_admin.py
    python manage_admin.py --username admin --email admin@defencepath.in --password MySecurePass123! --name "Administrator"
"""

import sys
import os
import argparse
import getpass
from werkzeug.security import generate_password_hash
import database

def provision_admin(username, email, password, full_name="System Administrator"):
    if not username or len(username) < 3:
        print("[ERROR] Username must be at least 3 characters.")
        return False
    if not email or "@" not in email:
        print("[ERROR] A valid email address is required.")
        return False
    if not password or len(password) < 6:
        print("[ERROR] Password must be at least 6 characters in length.")
        return False

    db = database.get_db()
    c = db.cursor()

    c.execute("SELECT id, username, role FROM users WHERE username = ? OR email = ?", (username, email))
    existing = c.fetchone()

    p_hash = generate_password_hash(password)

    if existing:
        user_id = existing['id']
        c.execute('''
        UPDATE users 
        SET full_name = ?, email = ?, password_hash = ?, role = 'admin'
        WHERE id = ?
        ''', (full_name, email, p_hash, user_id))
        db.commit()
        print(f"[SUCCESS] Existing account '{existing['username']}' updated to ADMINISTRATOR role.")
        print(f"[+] Admin ID: #ADM-00{user_id}")
        print(f"[+] Admin Username: {username}")
        print(f"[+] Admin Gateway: http://127.0.0.1:5000/admin/login")
    else:
        c.execute('''
        INSERT INTO users (username, full_name, email, password_hash, target_exam, role)
        VALUES (?, ?, ?, ?, 'Command HQ', 'admin')
        ''', (username, full_name, email, p_hash))
        db.commit()
        user_id = c.lastrowid
        print(f"[SUCCESS] New ADMINISTRATOR account created successfully.")
        print(f"[+] Admin ID: #ADM-00{user_id}")
        print(f"[+] Admin Username: {username}")
        print(f"[+] Admin Gateway: http://127.0.0.1:5000/admin/login")

    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DEFENCE PATH Admin Provisioning Utility")
    parser.add_argument('--username', help="Admin username")
    parser.add_argument('--email', help="Admin email address")
    parser.add_argument('--password', help="Admin password (if omitted, will prompt securely)")
    parser.add_argument('--name', default="System Administrator", help="Admin full name")

    args = parser.parse_args()

    if not args.username:
        print("=== DEFENCE PATH - Secure Administrator Provisioning ===")
        username = input("Enter Administrator Username: ").strip()
        email = input("Enter Administrator Email: ").strip()
        name = input("Enter Administrator Full Name [System Administrator]: ").strip() or "System Administrator"
        password = getpass.getpass("Enter Administrator Password: ")
        confirm = getpass.getpass("Confirm Administrator Password: ")
        if password != confirm:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)
        provision_admin(username, email, password, name)
    else:
        password = args.password
        if not password:
            password = getpass.getpass(f"Enter password for admin '{args.username}': ")
        provision_admin(args.username, args.email or f"{args.username}@defencepath.in", password, args.name)

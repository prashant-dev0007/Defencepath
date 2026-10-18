import os
import sys
import database
from app import app

if __name__ == '__main__':
    print("=" * 65)
    print("  DEFENCE PATH - FULL-STACK ARMED FORCES PORTAL")
    print("  'Your Dream. Your Discipline. Your Uniform.'")
    print("  Lead Architect & Developer: Er. Prashant Mishra")
    print("  Direct Contact Hotline: 6390314464")
    print("=" * 65)

    # Ensure DB is ready
    if not os.path.exists(database.DB_PATH):
        database.init_db()
        database.seed_data()

    port = int(os.environ.get("PORT", 5000))
    print(f"\n[+] DEFENCE PATH is active at: http://127.0.0.1:{port}")
    print("[+] Public & Aspirant Portal: http://127.0.0.1:5000/login")
    print("[+] Secure Admin Gateway: http://127.0.0.1:5000/admin/login")
    print("[+] Press Ctrl+C to terminate server.\n")

    app.run(host='0.0.0.0', port=port, debug=False)

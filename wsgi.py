"""
DEFENCE PATH - WSGI Entrypoint for Production Servers
Compatible with:
- Phusion Passenger (Hostinger Cloud / cPanel Python App)
- Gunicorn / uWSGI (Hostinger VPS / Ubuntu Linux / Nginx)
- Waitress / IIS (Windows Server)

Lead Architect & Developer: Er. Prashant Mishra (Ph: 6390314464)
"""

import os
import sys

# Ensure current application directory is in sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Initialize database schema and migrate safely if necessary
import database
if not os.path.exists(database.DB_PATH):
    database.init_db()
    database.seed_data()
else:
    database.migrate_db()

# Import Flask application instance
from app import app

# Standard WSGI aliases for web servers
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

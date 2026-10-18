# DEFENCE PATH - PRODUCTION DEPLOYMENT & HOSTING GUIDE
> **Full-Stack Indian Defence Recruitment Portal, PYQ Library, CBT Mock Test Platform & Admin CMS**  
> **Lead Architect & Developer:** Er. Prashant Mishra  
> **Direct Hotline:** 6390314464 | **UPI:** `pm204664-1@okaxis`

---

## 1. System Overview & Architecture

DEFENCE PATH is built with a high-performance, modular Python stack:
* **Backend:** Python 3.10+ with Flask 3.1 & Werkzeug 3.1.
* **Database:** SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and 30-second concurrency lock-wait timeout, enabling atomic reads and writes.
* **WSGI Server:** Gunicorn (Linux/Hostinger VPS) or Phusion Passenger (Hostinger Cloud / cPanel).
* **Reverse Proxy:** Nginx with Let's Encrypt HTTPS / SSL.
* **Document Engine:** ReportLab for authentic PDF generation of PYQ papers.
* **Authentication & Security:** PBKDF2-SHA256 password hashing, cryptographically random OTP generator, single-use token lifecycle, IDOR protections, and server-side CBT question sanitization (correct options are never sent to the candidate's browser).
* **Payments:** Scan-and-Pay UPI QR integration with 12-digit UTR validation and admin verification desk.
* **SEO Engine:** Dynamic `sitemap.xml`, `robots.txt`, Open Graph metadata, Twitter Cards, Schema.org JSON-LD structured data, and search-engine-friendly URLs (`/jobs`, `/exams`, `/pyq`, `/tests`).

---

## 2. Server Options Comparison

| Feature | Hostinger VPS (Ubuntu 22.04/24.04) *(Recommended)* | Hostinger Cloud / Shared (Passenger/cPanel) |
| :--- | :--- | :--- |
| **Performance** | Dedicated CPU/RAM, sub-second response times | Shared resources |
| **Background Crons** | Full Linux cron (`crontab -e`) | Scheduled tasks via hPanel |
| **Gunicorn Workers** | 3–4 asynchronous workers | Passenger managed workers |
| **SSL Setup** | Free automated Certbot / Let's Encrypt | 1-Click SSL in hPanel |
| **Control** | Full root SSH access | Web-based file manager & terminal |

---

## 3. Option A: Deployment on Hostinger VPS (Ubuntu 22.04 / 24.04)

### Step 1: Connect to your VPS via SSH
```bash
ssh root@YOUR_SERVER_IP
```

### Step 2: Install System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git sqlite3 libgl1-mesa-glx
```

### Step 3: Set Up Application Directory
```bash
mkdir -p /var/www/defencepath
cd /var/www/defencepath

# Clone your repository or upload files via SFTP:
# git clone <YOUR_REPO_URL> .

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Production Environment Variables
Create the production `.env` file from the provided template:
```bash
cp .env.example .env
nano .env
```
Fill in the live values:
```ini
FLASK_ENV=production
DEFENCE_PATH_SECRET_KEY=9f8c4b12a84d720b6e15904ca38150ecf5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0
PORT=5000
CANONICAL_DOMAIN=https://defencepath.in
SITE_NAME="DEFENCE PATH"

# SMTP Configuration (Required for Real Email OTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USER=your_verified_email@gmail.com
SMTP_PASSWORD=your_16_digit_app_password
SMTP_FROM_EMAIL=your_verified_email@gmail.com
SMTP_FROM_NAME="DEFENCE PATH Command"

# UPI Settings
UPI_ID=pm204664-1@okaxis
UPI_NAME="Er. Prashant Mishra"
MOCK_TEST_PRICE=5.0
DEVELOPER_PHONE=6390314464
```

### Step 5: Initialize and Migrate the Database
```bash
source venv/bin/activate
python -c "import database; database.init_db(); database.seed_data(); database.migrate_db()"
```

### Step 6: Create Systemd Service for Gunicorn
Create `/etc/systemd/system/defencepath.service`:
```ini
[Unit]
Description=DEFENCE PATH Flask Application Server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/defencepath
Environment="PATH=/var/www/defencepath/venv/bin"
ExecStart=/var/www/defencepath/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 wsgi:application --timeout 90 --access-logfile /var/log/defencepath_access.log --error-logfile /var/log/defencepath_error.log

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Set correct permissions, enable, and start the service:
```bash
sudo chown -R www-data:www-data /var/www/defencepath
sudo chmod -R 775 /var/www/defencepath/static/uploads
sudo chmod 664 /var/www/defencepath/defence_path.db
sudo systemctl daemon-reload
sudo systemctl enable defencepath
sudo systemctl start defencepath
sudo systemctl status defencepath
```

### Step 7: Configure Nginx as Reverse Proxy
Create `/etc/nginx/sites-available/defencepath`:
```nginx
server {
    server_name defencepath.in www.defencepath.in;

    # Maximum file upload size for payment proofs and question imports
    client_max_body_size 32M;

    # Static assets served directly by Nginx for maximum performance
    location /static/ {
        alias /var/www/defencepath/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy all dynamic requests to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}
```

Enable the site and test Nginx configuration:
```bash
sudo ln -s /etc/nginx/sites-available/defencepath /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 8: Install Free SSL Certificate via Certbot
```bash
sudo certbot --nginx -d defencepath.in -d www.defencepath.in --non-interactive --agree-tos -m your_email@gmail.com
```

---

## 4. Option B: Deployment on Hostinger Cloud / Shared Web Hosting (hPanel)

If you are using Hostinger Cloud Hosting or cPanel with the "Setup Python App" tool:

1. **Log in to Hostinger hPanel** -> Navigate to **Websites** -> **Manage**.
2. Scroll to **Advanced** -> Click **Setup Python App**.
3. Click **Create Application**:
   * **Python version:** Select **3.11** or **3.10**.
   * **Application root:** `/home/uXXXXX/public_html` or `/home/uXXXXX/defencepath`.
   * **Application URL:** `defencepath.in`.
   * **Application startup file:** `wsgi.py`.
   * **Application Entry point:** `application`.
4. Upload all project files into the Application Root directory using SFTP or File Manager.
5. In the Python App manager, enter the virtual environment command line:
   ```bash
   source /home/uXXXXX/virtualenv/defencepath/3.11/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
6. Place your `.env` file in the application root directory.
7. Click **Restart Application** in hPanel.

---

## 5. Domain & DNS Records Configuration

Configure the following DNS records at your domain registrar (Hostinger, GoDaddy, Cloudflare, etc.):

| Type | Host / Name | Value / Points To | TTL | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **A** | `@` | `YOUR_SERVER_PUBLIC_IP` | 300 / Auto | Primary domain resolution |
| **A** or **CNAME** | `www` | `YOUR_SERVER_PUBLIC_IP` or `defencepath.in` | 300 / Auto | WWW subdomain alias |
| **TXT** | `@` | `google-site-verification=...` | 300 / Auto | Google Search Console verification |

---

## 6. Real Email OTP Configuration (compulsory)

DEFENCE PATH enforces real email OTP dispatch for student and administrator password recovery.

### Using Google Gmail SMTP (Recommended):
1. Sign in to your Google Account and turn ON **2-Step Verification**:  
   [Google 2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification)
2. Generate an **App Password**:  
   Go to: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   * App Name: `Defence Path Production`
   * Click **Create**. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`).
3. Set in `.env`:
   ```ini
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USE_SSL=false
   SMTP_USER=your_gmail_address@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop
   SMTP_FROM_EMAIL=your_gmail_address@gmail.com
   SMTP_FROM_NAME="DEFENCE PATH Command"
   ```

### Using Hostinger Business Email (Titan Email):
```ini
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USE_TLS=false
SMTP_USE_SSL=true
SMTP_USER=contact@defencepath.in
SMTP_PASSWORD=your_email_account_password
SMTP_FROM_EMAIL=contact@defencepath.in
SMTP_FROM_NAME="DEFENCE PATH Command"
```

---

## 7. Automated Recruitment Updates & Crons

DEFENCE PATH includes a built-in automated synchronizer (`recruitment_updater.py`) that:
* Auto-expires old recruitment notices whose application deadlines have passed.
* Marks notices closing within 3 days as `Closing Soon`.
* Ingests verified official announcements and avoids duplicate records.
* Writes persistent audit logs to `recruitment_update_logs`.

### Set up Linux Cron Job:
Edit crontab:
```bash
sudo crontab -e
```
Add the following schedules:
```bash
# 1. Automatic Recruitment Deadline Sync every night at 2:00 AM
0 2 * * * /var/www/defencepath/venv/bin/python /var/www/defencepath/recruitment_updater.py >> /var/log/recruitment_sync.log 2>&1

# 2. Automated Point-in-Time Database Backup every night at 3:00 AM
0 3 * * * /var/www/defencepath/venv/bin/python /var/www/defencepath/backup_db.py >> /var/log/defencepath_backup.log 2>&1
```

---

## 8. Database Backup, Migration & Disaster Recovery

DEFENCE PATH includes a specialized atomic backup utility: `backup_db.py`.

### 1. Create On-Demand Database Backup:
```bash
python backup_db.py
```
This performs a non-blocking point-in-time snapshot of `defence_path.db` using SQLite's native C API and stores it in `backups/defence_path_backup_YYYYMMDD_HHMMSS.db`. It automatically retains the last 30 daily snapshots and rotates out older ones.

### 2. Restore Database from a Specific Snapshot:
```bash
python backup_db.py --restore backups/defence_path_backup_20261018_143333.db
```
The restore command automatically generates an emergency pre-restore snapshot before applying the target archive to prevent accidental data loss.

---

## 9. Google Search Console & SEO Verification

To ensure DEFENCE PATH is indexed on Google Search:

1. **Verify Sitemap & Robots:**
   * Sitemap URL: `https://defencepath.in/sitemap.xml`
   * Robots file: `https://defencepath.in/robots.txt`
2. **Submit to Google Search Console:**
   * Navigate to [https://search.google.com/search-console](https://search.google.com/search-console).
   * Choose **Domain** property -> enter `defencepath.in`.
   * Copy the TXT verification record and add it to your DNS zone in Hostinger.
   * Click **Verify**.
   * Under **Sitemaps**, submit: `sitemap.xml`.
3. **Structured Data Check:**
   * Test public pages using the [Google Rich Results Test](https://search.google.com/test/rich-results) to verify Schema.org `WebSite` and `EducationalOrganization` markup.

---

## 10. Post-Deployment Verification Checklist

Execute these verification checks immediately after deployment:

- [ ] **Home Page:** Opens over HTTPS (`https://defencepath.in`) with zero mixed-content warnings.
- [ ] **Developer Profile:** Displays Er. Prashant Mishra with contact hotline `6390314464`.
- [ ] **Syllabus Directory:** `/exams` lists authentic patterns for NDA, CDS, AFCAT, and Agniveer.
- [ ] **Candidate Registration & Login:** Student accounts can register, receive session cookies, and view their dashboard.
- [ ] **Forgot Password Flow:** Dispatches 6-digit OTP to user's real email inbox; OTP expires in 10 minutes; successfully updates password.
- [ ] **1 Free Mock Test Attempt:** Candidate takes 1 test without payment. Test finishes, saves score accurately, and marks `free_attempt_used = 1`.
- [ ] **CBT Examination Security:** Inspect browser dev tools -> Question network responses and JavaScript variables do NOT expose `correct_option` or explanations.
- [ ] **₹5 Paid Mock Test Flow:** Candidate attempting test #2 is routed to `/test-payment/<id>` with QR code and UPI ID `pm204664-1@okaxis`. Candidate submits UTR reference.
- [ ] **Admin Payment Desk:** Administrator signs in at `/admin/login`, views pending UTR at `/admin/payments`, clicks **Verify & Unlock**. Candidate's attempt is unlocked immediately.
- [ ] **Automated Recruitment Updater:** Runs via `python recruitment_updater.py` and creates an audit entry in `recruitment_update_logs`.
- [ ] **Automated Backup:** Runs via `python backup_db.py` and produces a timestamped `.db` snapshot in `backups/`.

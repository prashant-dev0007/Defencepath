import sqlite3
import os
import json
from datetime import datetime, date
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'defence_path.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Developer Profile Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS developer_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        title TEXT NOT NULL,
        contact_number TEXT NOT NULL,
        email TEXT DEFAULT NULL,
        profile_image TEXT NOT NULL,
        bio TEXT NOT NULL,
        qualification TEXT,
        portfolio_url TEXT,
        github_url TEXT,
        linkedin_url TEXT,
        visibility INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        target_exam TEXT DEFAULT 'NDA / CDS',
        role TEXT DEFAULT 'student', -- 'student' or 'admin'
        profile_image TEXT DEFAULT '/static/images/default_avatar.png',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 3. Defence Examinations Master Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS defence_exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        organization TEXT NOT NULL, -- Indian Army, Indian Navy, Indian Air Force, CAPF, Coast Guard
        category TEXT NOT NULL, -- Army, Navy, Air Force, CAPF, Coast Guard, Other
        description TEXT NOT NULL,
        eligibility_summary TEXT NOT NULL,
        min_age REAL NOT NULL,
        max_age REAL NOT NULL,
        age_relaxation_rules TEXT,
        educational_qualification TEXT NOT NULL,
        physical_standards TEXT,
        selection_stages TEXT,
        exam_pattern TEXT,
        official_portal_url TEXT,
        badge_color TEXT DEFAULT 'gold',
        is_active INTEGER DEFAULT 1
    )
    ''')

    # 4. Recruitment Notifications (Latest Jobs)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recruitments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        organization TEXT NOT NULL,
        post_name TEXT NOT NULL,
        category TEXT NOT NULL,
        qualification TEXT NOT NULL,
        min_age REAL NOT NULL,
        max_age REAL NOT NULL,
        age_relaxation TEXT,
        start_date TEXT NOT NULL,
        closing_date TEXT NOT NULL,
        exam_date TEXT,
        application_fee TEXT,
        selection_procedure TEXT,
        physical_requirements TEXT,
        medical_standards TEXT,
        notification_pdf_url TEXT,
        application_url TEXT,
        source_name TEXT NOT NULL,
        is_demo INTEGER DEFAULT 0,
        status TEXT NOT NULL, -- Currently Open, Upcoming, Closing Soon, Application Closed, Admit Card Released, Examination Date Announced, Result Declared
        vacancies INTEGER DEFAULT 0,
        last_verified TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 5. Official Portals Directory
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS official_portals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_name TEXT NOT NULL,
        category TEXT NOT NULL,
        official_website TEXT NOT NULL,
        recruitment_url TEXT NOT NULL,
        notification_url TEXT NOT NULL,
        apply_url TEXT NOT NULL,
        description TEXT NOT NULL,
        last_verified TEXT NOT NULL,
        logo_icon TEXT DEFAULT 'fa-shield-halved'
    )
    ''')

    # 6. PYQ Papers & Mock Tests
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS test_papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        exam_code TEXT NOT NULL,
        paper_type TEXT NOT NULL, -- 'PYQ' or 'MOCK'
        year INTEGER,
        subject TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        max_marks REAL NOT NULL,
        marks_per_correct REAL NOT NULL,
        negative_marks REAL NOT NULL,
        difficulty TEXT DEFAULT 'Moderate', -- Easy, Moderate, Hard
        languages TEXT DEFAULT 'English, Hindi',
        instructions TEXT,
        pdf_download_url TEXT,
        is_published INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 7. Questions Bank
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER,
        exam_code TEXT NOT NULL,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        difficulty TEXT DEFAULT 'Moderate',
        question_text_en TEXT NOT NULL,
        question_text_hi TEXT,
        option_a_en TEXT NOT NULL,
        option_a_hi TEXT,
        option_b_en TEXT NOT NULL,
        option_b_hi TEXT,
        option_c_en TEXT NOT NULL,
        option_c_hi TEXT,
        option_d_en TEXT NOT NULL,
        option_d_hi TEXT,
        correct_option TEXT NOT NULL, -- 'A', 'B', 'C', 'D'
        explanation_en TEXT NOT NULL,
        explanation_hi TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (paper_id) REFERENCES test_papers(id) ON DELETE CASCADE
    )
    ''')

    # 8. Test Attempts / Results
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS test_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        paper_id INTEGER NOT NULL,
        score REAL NOT NULL,
        max_marks REAL NOT NULL,
        total_questions INTEGER NOT NULL,
        correct_count INTEGER NOT NULL,
        incorrect_count INTEGER NOT NULL,
        unattempted_count INTEGER NOT NULL,
        accuracy_percent REAL NOT NULL,
        time_taken_seconds INTEGER NOT NULL,
        responses_json TEXT NOT NULL, -- json containing question_id -> {selected, is_correct, time}
        topic_stats_json TEXT, -- json summary by topic
        attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (paper_id) REFERENCES test_papers(id) ON DELETE CASCADE
    )
    ''')

    # 9. Saved Recruitment Notices (Bookmarks)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        recruitment_id INTEGER NOT NULL,
        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, recruitment_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (recruitment_id) REFERENCES recruitments(id) ON DELETE CASCADE
    )
    ''')

    # 10. Student Application Tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS application_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        exam_name TEXT NOT NULL,
        organization TEXT NOT NULL,
        application_date TEXT NOT NULL,
        status TEXT NOT NULL, -- Interested, Not Applied, Application Submitted, Fee Paid, Admit Card Available, Examination Completed, Result Awaited, Selected, Not Selected
        exam_date TEXT,
        admit_card_status TEXT DEFAULT 'Not Released',
        reference_number TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # 11. Study Planner Items
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS study_planner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        target_date TEXT NOT NULL,
        priority TEXT DEFAULT 'Medium', -- Low, Medium, High
        is_completed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # 12. Contact Messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        ip_address TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 13. System Announcements
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'Update',
        content TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

def seed_data():
    conn = get_db()
    cursor = conn.cursor()

    # Seed Developer Profile if empty
    cursor.execute("SELECT COUNT(*) FROM developer_profile")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO developer_profile (
            name, title, contact_number, email, profile_image,
            bio, qualification, portfolio_url, github_url, linkedin_url, visibility
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
        ''', (
            "Er. Prashant Mishra",
            "Project Developer – Defence Path",
            "6390314464",
            None, # "Developer email will be available soon" per instruction
            "/static/uploads/developer/prashant_image.jpeg",
            "Er. Prashant Mishra is a dedicated software engineer and full-stack system architect passionate about empowering Indian defence aspirants. DEFENCE PATH is conceived and engineered to bridge the information and preparation gap for lakhs of youth aspiring to earn the prestigious uniform across the Indian Armed Forces (Army, Navy, Air Force) and Central Armed Police Forces. The platform integrates real-time recruitment tracking, authentic CBT examination engines, verified PYQs, and actionable weakness analytics.",
            "B.Tech in Computer Science & Engineering",
            "https://defencepath.portal",
            "https://github.com/prashantmishra",
            "https://linkedin.com/in/prashantmishra",
            1
        ))

    # Seed Default Users (Admin & Aspirant)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Admin Account (Er. Prashant Mishra)
        admin_pass = generate_password_hash("admin123")
        cursor.execute('''
        INSERT INTO users (username, full_name, email, password_hash, phone, target_exam, role, profile_image)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "admin",
            "Er. Prashant Mishra",
            "admin@defencepath.in",
            admin_pass,
            "6390314464",
            "Administrator",
            "admin",
            "/static/uploads/developer/prashant_image.jpeg"
        ))

        # Aspirant Account
        student_pass = generate_password_hash("aspirant123")
        cursor.execute('''
        INSERT INTO users (username, full_name, email, password_hash, phone, target_exam, role, profile_image)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "aspirant",
            "Captain Vikram Sharma",
            "vikram@aspirant.defencepath.in",
            student_pass,
            "9876543210",
            "NDA & CDS Army Entry",
            "student",
            "/static/images/cadet_avatar.png"
        ))

    # Seed Official Portals
    cursor.execute("SELECT COUNT(*) FROM official_portals")
    if cursor.fetchone()[0] == 0:
        portals = [
            ("Indian Army (Officers & JCO/OR)", "Army", "https://joinindianarmy.nic.in", "https://joinindianarmy.nic.in/default.aspx", "https://joinindianarmy.nic.in/notification-officers.htm", "https://joinindianarmy.nic.in/Authentication.aspx", "Official recruitment website of the Indian Army for Agniveer entries, TGC, SSC Tech, NDA, CDS and direct officer entries.", "15-Oct-2026", "fa-shield-halved"),
            ("Indian Navy", "Navy", "https://joinindiannavy.gov.in", "https://joinindiannavy.gov.in/en/account/account/state", "https://joinindiannavy.gov.in/en/announcement", "https://joinindiannavy.gov.in/en/account/login", "Join Indian Navy portal for Agniveer SSR, Agniveer MR, Executive/Technical Officer Entries and 10+2 B.Tech Cadet scheme.", "15-Oct-2026", "fa-anchor"),
            ("Indian Air Force (Officers)", "Air Force", "https://careerindianairforce.cdac.in", "https://afcat.cdac.in/AFCAT/", "https://afcat.cdac.in/AFCAT/notifications.html", "https://afcat.cdac.in/afcatreg/", "Air Force Common Admission Test (AFCAT) and officer commissioning for Flying, Technical and Ground Duty branches.", "15-Oct-2026", "fa-jet-fighter"),
            ("Indian Air Force (Agniveervayu)", "Air Force", "https://agnipathvayu.cdac.in", "https://agnipathvayu.cdac.in/AV/", "https://agnipathvayu.cdac.in/AV/notifications", "https://agnipathvayu.cdac.in/AV/candidate/login", "Official portal for Agniveervayu intake (Science & Other than Science subjects) under the Agnipath scheme.", "15-Oct-2026", "fa-plane"),
            ("Union Public Service Commission (UPSC)", "UPSC", "https://upsc.gov.in", "https://upsconline.nic.in", "https://upsc.gov.in/examinations/active-examinations", "https://upsconline.nic.in/upsc/OTRP/", "Conducting body for NDA & NA, CDS Examination, CAPF (Assistant Commandants), and Combined Defence Services.", "15-Oct-2026", "fa-building-columns"),
            ("Staff Selection Commission (SSC)", "SSC", "https://ssc.gov.in", "https://ssc.gov.in/candidate-portal", "https://ssc.gov.in/notices", "https://ssc.gov.in/login", "Apex examination body for SSC GD Constable in BSF, CISF, CRPF, ITBP, SSB, SSF and Rifleman in Assam Rifles.", "15-Oct-2026", "fa-id-card"),
            ("Indian Coast Guard (ICG)", "Coast Guard", "https://joinindiancoastguard.cdac.in", "https://joinindiancoastguard.cdac.in/cgept/", "https://joinindiancoastguard.cdac.in/cgept/notifications.html", "https://joinindiancoastguard.cdac.in/cgept/candidate/login", "Recruitment portal for Navik (General Duty), Navik (Domestic Branch) and Yantrik in the Indian Coast Guard.", "15-Oct-2026", "fa-compass"),
            ("Central Reserve Police Force (CRPF)", "CAPF", "https://rect.crpf.gov.in", "https://crpf.gov.in/recruitment.htm", "https://rect.crpf.gov.in/notifications", "https://rect.crpf.gov.in", "Official recruitment cell for CRPF Sub-Inspectors, Head Constables, Signal Staff and General Duty trades.", "15-Oct-2026", "fa-user-shield"),
            ("Border Security Force (BSF)", "CAPF", "https://rectt.bsf.gov.in", "https://bsf.gov.in/recruitment", "https://rectt.bsf.gov.in/notifications", "https://rectt.bsf.gov.in", "Official recruitment wing for India's First Line of Defence: BSF Water Wing, Air Wing, Engineering and GD.", "15-Oct-2026", "fa-person-military-pointing"),
            ("Central Industrial Security Force (CISF)", "CAPF", "https://cisfrectt.cisf.gov.in", "https://cisfrectt.cisf.gov.in", "https://cisfrectt.cisf.gov.in/notification.php", "https://cisfrectt.cisf.gov.in", "Recruitment authority for CISF Assistant Sub-Inspector, Head Constable Ministerial and Fireman cadres.", "15-Oct-2026", "fa-shield-halved"),
            ("Indo-Tibetan Border Police (ITBP)", "CAPF", "https://recruitment.itbpolice.nic.in", "https://itbpolice.nic.in", "https://recruitment.itbpolice.nic.in/notifications", "https://recruitment.itbpolice.nic.in", "High-altitude border force recruitment for Telecommunication, Tradesmen, Animal Transport and Officers.", "15-Oct-2026", "fa-mountain"),
            ("Assam Rifles (The Sentinels of Northeast)", "Army", "https://assamrifles.gov.in", "https://assamrifles.gov.in/recruitment", "https://assamrifles.gov.in/notifications", "https://assamrifles.gov.in/onlineapp", "Oldest paramilitary force of India recruiting Technical and Tradesmen Personnel and GD Riflemen.", "15-Oct-2026", "fa-medal")
        ]
        for p in portals:
            cursor.execute('''
            INSERT INTO official_portals (org_name, category, official_website, recruitment_url, notification_url, apply_url, description, last_verified, logo_icon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', p)

    # Seed Defence Exams Master
    cursor.execute("SELECT COUNT(*) FROM defence_exams")
    if cursor.fetchone()[0] == 0:
        exams = [
            (
                "NDA", "National Defence Academy & Naval Academy", "UPSC / Tri-Services", "Tri-Services",
                "Premier joint training academy for Army, Navy and Air Force cadets conducted twice a year by UPSC.",
                "10+2 passed/appearing. Age 16.5 to 19.5 years. Unmarried male and female candidates.",
                16.5, 19.5, "Strict date-of-birth bracket as per UPSC notification (no category relaxation for entry age).",
                "Army Wing: 12th Class pass of 10+2 pattern or equivalent. Air Force & Naval Wings: 12th Class pass with Physics, Chemistry and Mathematics.",
                "Minimum Height: 157 cm (Army/Navy), 162.5 cm (Air Force Flying). Gorkhas and North-Eastern candidates receive relaxation (152 cm).",
                "Written Examination (Mathematics 300 marks + GAT 600 marks = 900 marks) -> 5-Day SSB Interview (900 marks) -> Medical Board.",
                "Paper 1: Mathematics (120 Questions, 300 Marks, 2.5 Hrs, -0.83 neg). Paper 2: General Ability Test (150 Questions, 600 Marks, 2.5 Hrs, -1.33 neg).",
                "https://upsconline.nic.in", "gold"
            ),
            (
                "CDS", "Combined Defence Services Examination", "UPSC / Tri-Services", "Tri-Services",
                "Direct entry for university graduates into IMA Dehradun, INA Ezhimala, AFA Hyderabad, and OTA Chennai.",
                "Graduates / Final Year Degree students. Age 19 to 24 (IMA/INA/AFA) and 19 to 25 (OTA).",
                19.0, 25.0, "OTA: 19 to 25 years. IMA: 19 to 24 years. Naval Academy: 19 to 24 years (Engineering degree). Air Force: 20 to 24 years.",
                "IMA & OTA: Degree of a recognized University or equivalent. INA: Degree in Engineering. AFA: Degree with Physics & Math at 10+2 level or B.E./B.Tech.",
                "Height: 157.5 cm (IMA/OTA), 157 cm (INA), 162.5 cm with Leg length 99-120 cm (AFA).",
                "Written Examination -> 5-Day SSB Interview -> Comprehensive Special Medical Examination.",
                "IMA/INA/AFA: English (100m) + GK (100m) + Elementary Maths (100m) = 300m. OTA: English (100m) + GK (100m) = 200m. Negative marking: 1/3rd.",
                "https://upsconline.nic.in", "gold"
            ),
            (
                "AFCAT", "Air Force Common Admission Test", "Indian Air Force", "Air Force",
                "Officer entry for Flying Branch and Ground Duty (Technical & Non-Technical) branches of the Indian Air Force.",
                "Graduate with minimum 60% marks and 10+2 with 50% in Maths & Physics.",
                20.0, 26.0, "Flying Branch: 20 to 24 years. Ground Duty (Tech & Non-Tech): 20 to 26 years.",
                "Flying Branch: 10+2 with 50% each in Maths & Physics + Graduation with min 60% or B.E./B.Tech min 60%. Ground Duty Tech: 4-yr Engineering degree min 60%.",
                "Flying: 162.5 cm, Leg Length min 99 cm, max 120 cm. Ground Duty: Men 157.5 cm, Women 152 cm.",
                "Online CBT Examination -> AFSB Interview (Stage 1 Screening + Stage 2 Psychology, GTO, Interview & CPSS for Flying) -> Medicals.",
                "100 Questions, 300 Marks, 2 Hours. Subjects: General Awareness, Verbal Ability, Numerical Ability, Reasoning & Military Aptitude. (+3 / -1).",
                "https://afcat.cdac.in", "blue"
            ),
            (
                "AGNIVEER_ARMY_GD", "Agniveer General Duty (Indian Army)", "Indian Army", "Army",
                "Core fighting soldier entry in Infantry, Artillery, Armoured Corps and operational arms under Agnipath scheme.",
                "Class 10th / Matric with 45% marks in aggregate and 33% in each subject.",
                17.5, 21.0, "Age 17.5 to 21 years across all categories as per Agnipath scheme rules.",
                "Class 10th / Matric with 45% marks in aggregate and 33% in each subject. For boards following grading system, min D grade in individual subjects.",
                "Height: 169-170 cm (varies by region/zone). Chest: 77 cm + 5 cm expansion. 1.6 Km run in 5 min 30 sec (Group 1 - 60 marks) + 10 Pull-ups (40 marks).",
                "Phase 1: Online Common Entrance Exam (CEE) -> Phase 2: Recruitment Rally (Physical Fitness Test PFT + Physical Measurement Test PMT) -> Phase 3: Medical Exam.",
                "50 Questions, 100 Marks, 60 Minutes. General Knowledge (15 Q, 30 M), General Science (15 Q, 30 M), Math (15 Q, 30 M), Logical Reasoning (5 Q, 10 M). Neg: 0.5.",
                "https://joinindianarmy.nic.in", "green"
            ),
            (
                "AGNIVEER_ARMY_TECH", "Agniveer Technical (Indian Army)", "Indian Army", "Army",
                "Technical specialists serving in Corps of Signals, EME, Engineers and Air Defence units.",
                "10+2 Intermediate in Science with Physics, Chemistry, Maths and English with 50% marks.",
                17.5, 21.0, "Age 17.5 to 21 years as per official notification.",
                "10+2 / Intermediate Exam Pass in Science with Physics, Chemistry, Maths and English with 50% marks in aggregate and 40% in each subject.",
                "Height: 169 cm (regional criteria apply). Chest: 77 cm + 5 cm expansion. Physical Fitness Qualifying (1.6 km run & pull ups).",
                "Online CEE -> Physical Rally -> Adaptability Test -> Medical Examination.",
                "50 Questions, 200 Marks, 60 Minutes. GK (10 Q), Maths (15 Q), Physics (15 Q), Chemistry (10 Q). (+4 marks per correct, -1 mark negative).",
                "https://joinindianarmy.nic.in", "green"
            ),
            (
                "AGNIVEER_NAVY_SSR", "Agniveer (SSR) - Senior Secondary Recruit", "Indian Navy", "Navy",
                "Key sailor cadre operating modern naval weaponry, sensor suites, radar, sonar and warship systems.",
                "10+2 with Mathematics & Physics with at least one of Chemistry/Biology/Computer Science.",
                17.5, 21.0, "17.5 to 21 years on the date of enrolment.",
                "Qualified in 10+2 examination with Maths & Physics and at least one of these subjects: Chemistry/Biology/Computer Science from an approved board.",
                "Height: Male 157 cm, Female 152 cm. PFT: 1.6 Km run (6.5 min male, 8 min female), Squats (20 male, 15 female), Push-ups 12 (male).",
                "Shortlisting via Computer-Based Test (INET) -> Stage II PFT, Written Exam & Recruitment Medical -> Stage III Final Enrolment Medical at INS Chilka.",
                "100 Questions, 100 Marks, 60 Minutes. English (25 Q), Science (25 Q), Mathematics (25 Q), General Awareness (25 Q). (+1 / -0.25).",
                "https://joinindiannavy.gov.in", "cyan"
            ),
            (
                "AGNIVEERVAYU", "Agniveervayu (Science & Other than Science)", "Indian Air Force", "Air Force",
                "Frontline airmen cadres serving in IAF technical trades, radar operation, air traffic support, and administration.",
                "10+2 with Maths, Physics & English min 50% OR 3-year Diploma in Engineering with 50%.",
                17.5, 21.0, "Age 17.5 to 21 years.",
                "Science Subjects: 10+2 with Mathematics, Physics and English with min 50% marks. Other than Science: 10+2 in any stream with min 50% and 50% in English.",
                "Height: 152.5 cm min. Chest: Minimum 5 cm expansion. 1.6 Km run in 7 minutes, 10 Push-ups, 10 Sit-ups, 20 Squats.",
                "Phase I: Online CBT -> Phase II: Physical Fitness Test (PFT), Adaptability Test-I & II -> Phase III: Medical Examination.",
                "Science: 70 Qs (Maths 25, Physics 25, English 20), 60 mins. Both Science & Other: 100 Qs, 85 mins. (+1 / -0.25).",
                "https://agnipathvayu.cdac.in", "blue"
            ),
            (
                "CAPF_AC", "Central Armed Police Forces (Assistant Commandant)", "UPSC / MHA", "CAPF",
                "Direct Gazette Officer commissioning into BSF, CRPF, CISF, ITBP and SSB.",
                "Bachelor's Degree in any discipline from a recognized university.",
                20.0, 25.0, "SC/ST: up to 5 years relaxation (30 yrs). OBC: up to 3 years relaxation (28 yrs). Ex-Servicemen: up to 5 years.",
                "A candidate must hold a Bachelor's degree of a University incorporated by an Act of the Central or State Legislature.",
                "Men: Height 165 cm, Chest 81 cm (+5cm). Women: Height 157 cm. 100m race (16s men, 18s women), 800m race (3m 45s men, 4m 45s women), Long Jump, Shot Put.",
                "Paper I (General Ability & Intelligence - 250m) + Paper II (General Studies, Essay & Comprehension - 200m) -> Physical & Medical -> Interview/Personality (150m).",
                "Paper I: 125 Objective Questions, 250 Marks, 2 Hours, -1/3rd negative. Paper II: Conventional descriptive format, 200 Marks, 3 Hours.",
                "https://upsconline.nic.in", "orange"
            ),
            (
                "SSC_GD", "SSC GD Constable (Paramilitary & Assam Rifles)", "Staff Selection Commission", "CAPF",
                "Constable General Duty in BSF, CISF, CRPF, ITBP, SSB, SSF and Rifleman in Assam Rifles.",
                "Matriculation or 10th Class pass from a recognized Board/University.",
                18.0, 23.0, "SC/ST: +5 years (28 yrs). OBC: +3 years (26 yrs). Ex-Servicemen: +3 years.",
                "Candidates must have passed Matriculation or 10th Class Examination from a recognized Board/University on or before the crucial date.",
                "Male: Height 170 cm, Chest 80 cm (+5cm). Female: Height 157 cm. Physical Efficiency: Male 5 Km run in 24 mins, Female 1.6 Km run in 8.5 mins.",
                "Computer Based Examination (CBE) -> Physical Efficiency Test (PET) / Physical Standard Test (PST) -> Detailed Medical Examination (DME) -> Document Verification.",
                "80 Questions, 160 Marks, 60 Minutes. Reasoning (20 Q, 40 M), GK (20 Q, 40 M), Elementary Maths (20 Q, 40 M), English/Hindi (20 Q, 40 M). Neg: 0.25 per wrong.",
                "https://ssc.gov.in", "emerald"
            ),
            (
                "COAST_GUARD_GD", "Navik General Duty (Indian Coast Guard)", "Indian Coast Guard", "Coast Guard",
                "Maritime protection force personnel operating offshore patrol vessels, interceptor boats, and coastal surveillance.",
                "10+2 with Maths and Physics from an education board recognized by COBSE.",
                18.0, 22.0, "SC/ST: 5 years relaxation. OBC: 3 years relaxation.",
                "10+2 passed with Maths and Physics from an education board recognized by Council of Boards for School Education (COBSE).",
                "Height: 157 cm minimum. Chest: Proportionate with min 5 cm expansion. 1.6 Km run in 7 mins, 20 Squats (Uthak Baithak), 10 Push-ups.",
                "Stage-I Computer Based Test (Section I + Section II) -> Stage-II PFT, Document Verification & Initial Medical -> Stage-III Final Medical at INS Chilka.",
                "Section I: 60 Qs, 60 Marks, 45 Mins. Section II: 50 Qs (Maths 25, Physics 25), 50 Marks, 30 Mins. No negative marking.",
                "https://joinindiancoastguard.cdac.in", "blue"
            )
        ]
        for e in exams:
            cursor.execute('''
            INSERT INTO defence_exams (
                code, name, organization, category, description,
                eligibility_summary, min_age, max_age, age_relaxation_rules,
                educational_qualification, physical_standards, selection_stages,
                exam_pattern, official_portal_url, badge_color
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', e)

    # Seed Recruitments (Latest Defence Jobs)
    cursor.execute("SELECT COUNT(*) FROM recruitments")
    if cursor.fetchone()[0] == 0:
        recruits = [
            (
                "UPSC NDA & NA (I) 2026 Examination", "Union Public Service Commission", "Cadet - Army, Navy & Air Force Wings", "Tri-Services",
                "12th Pass / Appearing (10+2 pattern)", 16.5, 19.5, "Strict DOB bracket: 02 July 2007 to 01 July 2010 (No category relaxation)",
                "2026-10-01", "2026-11-10", "2027-04-18", "Rs. 100/- (Female/SC/ST candidates exempted)",
                "Written Exam (900 Marks) -> SSB Interview (900 Marks) -> Medical Examination",
                "Height: 157 cm (162.5 cm for Flying). Visual Acuity: 6/6 in better eye.",
                "Medical standards strictly governed by Defence Medical Board manuals.",
                "https://upsc.gov.in/sites/default/files/Notice-NDA-NA-I-2026-Eng.pdf",
                "https://upsconline.nic.in/upsc/OTRP/",
                "UPSC Official Notification Portal", 0, "Currently Open", 400, "15-Oct-2026"
            ),
            (
                "UPSC CDS (I) 2026 Examination (IMA, INA, AFA, OTA)", "Union Public Service Commission", "Commissioned Officer (Lieutenant / Sub-Lieutenant / Flying Officer)", "Tri-Services",
                "Degree of recognized University (Engineering for INA/AFA)", 19.0, 25.0, "OTA: up to 25 yrs. IMA/INA: up to 24 yrs. AFA: up to 24 yrs (26 with Commercial Pilot Licence).",
                "2026-10-05", "2026-11-15", "2027-04-18", "Rs. 200/- (Female/SC/ST exempted)",
                "Written Examination -> SSB Interview -> Medical Board",
                "Height: 157.5 cm (Army/Navy), 162.5 cm (AFA).",
                "Comprehensive military medical board at military hospital.",
                "https://upsc.gov.in/sites/default/files/Notice-CDS-I-2026-Eng.pdf",
                "https://upsconline.nic.in",
                "UPSC Official Gazette", 0, "Currently Open", 457, "15-Oct-2026"
            ),
            (
                "Indian Army Agniveer Intake Rally 2026-27 (All Zones)", "Indian Army", "Agniveer General Duty, Technical & Tradesmen", "Army",
                "10th Pass (45% agg) for GD; 10+2 Science (PCM 50%) for Tech; 8th/10th for Tradesman", 17.5, 21.0, "Age 17.5 to 21 years on date of enrollment across all categories.",
                "2026-09-15", "2026-10-30", "2026-12-10", "Rs. 250/- online examination fee",
                "Phase I: Online CEE -> Phase II: Physical Fitness Test (PFT) -> Medical",
                "1.6 Km run in 5m 30s (Group I: 60 marks), 10 Beam Pull-ups (40 marks), 9-ft ditch jump, zig-zag balance.",
                "Standard military medical examination at rally site.",
                "https://joinindianarmy.nic.in/Agniveer_Notification_2026.pdf",
                "https://joinindianarmy.nic.in/Authentication.aspx",
                "Join Indian Army Official Portal", 0, "Closing Soon", 25000, "15-Oct-2026"
            ),
            (
                "AFCAT 01/2026 Indian Air Force Officer Entry", "Indian Air Force", "Flying Branch & Ground Duty (Tech & Non-Tech)", "Air Force",
                "Graduation min 60% with Maths & Physics at 10+2 OR B.E./B.Tech min 60%", 20.0, 26.0, "Flying: 20-24 yrs; Ground Duty: 20-26 yrs.",
                "2026-11-01", "2026-11-30", "2027-02-20", "Rs. 550/- for all candidates",
                "Online CBT (100 Qs, 300 Marks) -> AFSB Interview (Stage 1 & 2) -> Medical Board",
                "Men: 157.5 cm min. Women: 152 cm. Flying branch: 162.5 cm with specific leg length.",
                "CPSS test for Flying Branch; IAM/CME Air Force medical board.",
                "https://afcat.cdac.in/AFCAT/assets/images/news/AFCAT_01_2026.pdf",
                "https://afcat.cdac.in/afcatreg/",
                "Air Force AFCAT Portal", 0, "Upcoming", 317, "15-Oct-2026"
            ),
            (
                "Indian Navy Agniveer (SSR & MR) 01/2026 Batch", "Indian Navy", "Sailor - SSR (Senior Secondary) & MR (Matric Recruit)", "Navy",
                "10+2 with Maths & Physics (SSR); 10th Pass (MR)", 17.5, 21.0, "Age 17.5 to 21 years at date of course commencement.",
                "2026-10-10", "2026-11-05", "2026-12-28", "Rs. 550/- + 18% GST",
                "Stage I: INET CBT -> Stage II: Physical Fitness Test & Written Test -> Final Medical at INS Chilka",
                "Male: 157 cm, Female: 152 cm. 1.6 Km run in 6m 30s.",
                "Visual standards 6/6 without glasses for SSR operations.",
                "https://joinindiannavy.gov.in/files/SSR_MR_01_2026.pdf",
                "https://joinindiannavy.gov.in/en/account/login",
                "Join Indian Navy Recruitment Cell", 0, "Currently Open", 4100, "15-Oct-2026"
            ),
            (
                "SSC GD Constable 2026-27 in CAPFs, SSF & Assam Rifles", "Staff Selection Commission", "Constable (General Duty)", "CAPF",
                "Matriculation or 10th Class pass from recognized Board", 18.0, 23.0, "SC/ST: 5 years relaxation (28 yrs); OBC: 3 years (26 yrs); Ex-Servicemen: 3 years.",
                "2026-08-20", "2026-10-14", "2027-01-15", "Rs. 100/- (Women, SC, ST, ESM exempted)",
                "Computer Based Examination (CBE) -> PET/PST -> Medical Examination -> Document Verification",
                "Male: Height 170 cm, Chest 80 cm (+5cm). Female: Height 157 cm. 5 Km run in 24 mins for male.",
                "Strict CAPF medical manual standards.",
                "https://ssc.gov.in/notices/SSC_GD_2026_Notice.pdf",
                "https://ssc.gov.in/login",
                "SSC Official Portal", 0, "Application Closed", 39481, "15-Oct-2026"
            ),
            (
                "UPSC CAPF (Assistant Commandants) 2026", "Union Public Service Commission", "Assistant Commandant (Group A Gazette Officer)", "CAPF",
                "Bachelor's Degree in any discipline", 20.0, 25.0, "SC/ST: 5 yrs (30 yrs); OBC: 3 yrs (28 yrs); Central Govt employees / Civilian: up to 5 yrs.",
                "2026-04-20", "2026-05-15", "2026-08-03", "Rs. 200/- (Female/SC/ST exempted)",
                "Paper I (General Ability & Intelligence) + Paper II (Descriptive) -> PET/PST -> Personality Interview",
                "Male: Height 165 cm, Chest 81 cm (+5cm). Female: Height 157 cm. 100m in 16s, 800m in 3m 45s.",
                "Standard Category I Central Armed Police medical norms.",
                "https://upsc.gov.in/sites/default/files/Notice-CAPF-2026-Eng.pdf",
                "https://upsconline.nic.in",
                "UPSC Gazette Notification", 0, "Admit Card Released", 506, "15-Oct-2026"
            ),
            (
                "Indian Coast Guard Navik (GD) 01/2027 Batch", "Indian Coast Guard", "Navik (General Duty) & Yantrik", "Coast Guard",
                "10+2 with Maths & Physics (Navik GD); 10th + Engineering Diploma (Yantrik)", 18.0, 22.0, "SC/ST: 5 years; OBC: 3 years.",
                "2026-11-15", "2026-12-05", "2027-03-10", "Rs. 300/- (SC/ST exempted)",
                "Stage I: CBT Exam -> Stage II: PFT & Document Verification -> Stage III: Final Enrolment Medical",
                "Height 157 cm min. 1.6 Km run in 7 mins, 20 Squats, 10 Push-ups.",
                "Distant vision 6/6 (better eye) and 6/9 (worse eye).",
                "https://joinindiancoastguard.cdac.in/cgept/notifications/Navik_01_2027.pdf",
                "https://joinindiancoastguard.cdac.in/cgept/candidate/login",
                "Indian Coast Guard Official C-DAC", 0, "Upcoming", 350, "15-Oct-2026"
            )
        ]
        for r in recruits:
            cursor.execute('''
            INSERT INTO recruitments (
                title, organization, post_name, category, qualification,
                min_age, max_age, age_relaxation, start_date, closing_date,
                exam_date, application_fee, selection_procedure, physical_requirements,
                medical_standards, notification_pdf_url, application_url, source_name,
                is_demo, status, vacancies, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', r)

    # Seed Test Papers & Questions
    cursor.execute("SELECT COUNT(*) FROM test_papers")
    if cursor.fetchone()[0] == 0:
        papers = [
            (
                "NDA 2024 (I) - Mathematics Authentic PYQ Full Test",
                "NDA", "PYQ", 2024, "Mathematics", 150, 120, 300.0, 2.5, 0.83, "Moderate",
                "English, Hindi", "Authentic UPSC NDA Previous Year Paper. 2.5 marks for correct response, -0.83 marks negative marking for incorrect answer.",
                "/static/downloads/nda_maths_2024_pyq.pdf", 1
            ),
            (
                "NDA 2024 (I) - General Ability Test (GAT) Authentic PYQ",
                "NDA", "PYQ", 2024, "General Ability", 150, 150, 600.0, 4.0, 1.33, "Moderate",
                "English, Hindi", "Authentic UPSC NDA GAT Paper covering English (50 Qs) and General Knowledge (100 Qs). +4 marks per correct, -1.33 marks negative.",
                "/static/downloads/nda_gat_2024_pyq.pdf", 1
            ),
            (
                "CDS 2024 (II) - Elementary Mathematics Standard Practice Mock",
                "CDS", "MOCK", 2024, "Mathematics", 120, 100, 100.0, 1.0, 0.33, "Hard",
                "English, Hindi", "Standard CDS Elementary Mathematics examination pattern following exact UPSC syllabus. +1 mark for correct, -0.33 for wrong.",
                "/static/downloads/cds_maths_mock.pdf", 1
            ),
            (
                "Indian Army Agniveer GD - Full All-India Mock Test 01",
                "AGNIVEER_ARMY_GD", "MOCK", 2025, "All Subjects", 60, 50, 100.0, 2.0, 0.50, "Moderate",
                "English, Hindi", "Comprehensive mock test for Agniveer GD: GK (15 Qs), General Science (15 Qs), Maths (15 Qs), Logical Reasoning (5 Qs). +2 / -0.5.",
                "/static/downloads/agniveer_gd_mock_01.pdf", 1
            ),
            (
                "AFCAT 2024 (II) - Reasoning & Military Aptitude Practice Set",
                "AFCAT", "PYQ", 2024, "Reasoning & Aptitude", 120, 100, 300.0, 3.0, 1.00, "Moderate",
                "English", "Authentic AFCAT examination pattern: Verbal Ability, Numerical Ability, Reasoning and Military Aptitude. +3 / -1 mark.",
                "/static/downloads/afcat_2024_paper.pdf", 1
            ),
            (
                "SSC GD Constable 2024 - Full Practice Test Set A",
                "SSC_GD", "PYQ", 2024, "All Subjects", 60, 80, 160.0, 2.0, 0.25, "Easy",
                "English, Hindi", "Exact SSC GD CBT Pattern: Reasoning (20), GK (20), Elementary Maths (20), English/Hindi (20). +2 marks, -0.25 negative.",
                "/static/downloads/ssc_gd_set_a.pdf", 1
            )
        ]
        for p in papers:
            cursor.execute('''
            INSERT INTO test_papers (
                title, exam_code, paper_type, year, subject, duration_minutes,
                total_questions, max_marks, marks_per_correct, negative_marks,
                difficulty, languages, instructions, pdf_download_url, is_published
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', p)

    # Seed rich Question Bank with detailed explanations, steps, and topic categorization!
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        # We will associate questions with Paper 1 (NDA Maths), Paper 2 (NDA GAT), Paper 4 (Agniveer GD), etc.
        # Let's fetch the paper IDs
        cursor.execute("SELECT id, exam_code, paper_type, title FROM test_papers ORDER BY id ASC")
        all_papers = cursor.fetchall()
        p1_id = all_papers[0]['id'] # NDA Maths
        p2_id = all_papers[1]['id'] # NDA GAT
        p3_id = all_papers[2]['id'] # CDS Maths
        p4_id = all_papers[3]['id'] # Agniveer GD
        p5_id = all_papers[4]['id'] # AFCAT
        p6_id = all_papers[5]['id'] # SSC GD

        questions_list = [
            # Paper 1: NDA Mathematics
            (
                p1_id, "NDA", "Mathematics", "Trigonometry", "Moderate",
                "What is the value of sin(15°) + cos(15°)?",
                "sin(15°) + cos(15°) का मान क्या है?",
                "1 / √2", "1 / √2",
                "√(3/2)", "√(3/2)",
                "√3 / 2", "√3 / 2",
                "√2", "√2",
                "B",
                "Step-by-step Solution:\nLet S = sin(15°) + cos(15°).\nSquaring both sides: S² = (sin 15° + cos 15°)² = sin²(15°) + cos²(15°) + 2 sin(15°) cos(15°)\nSince sin²θ + cos²θ = 1 and 2 sin θ cos θ = sin(2θ):\nS² = 1 + sin(30°) = 1 + 1/2 = 3/2.\nTaking positive square root (as both sin 15° and cos 15° are positive in the first quadrant):\nS = √(3/2).\nTherefore, Option B is correct.",
                "चरणबद्ध हल:\nमाना S = sin(15°) + cos(15°).\nदोनों पक्षों का वर्ग करने पर: S² = sin²(15°) + cos²(15°) + 2 sin(15°) cos(15°) = 1 + sin(30°) = 1 + 1/2 = 3/2.\nअतः S = √(3/2). विकल्प B सही है।"
            ),
            (
                p1_id, "NDA", "Mathematics", "Quadratic Equations", "Moderate",
                "If the roots of the equation x² - px + q = 0 differ by unity, then which one of the following relations is correct?",
                "यदि समीकरण x² - px + q = 0 के मूलों का अंतर 1 (इकाई) है, तो निम्नलिखित में से कौन सा संबंध सही है?",
                "p² = 4q + 1", "p² = 4q + 1",
                "p² = 4q - 1", "p² = 4q - 1",
                "q² = 4p + 1", "q² = 4p + 1",
                "p² + 4q = 1", "p² + 4q = 1",
                "A",
                "Step-by-step Solution:\nLet roots be α and β.\nGiven: |α - β| = 1.\nFrom Vieta's formulas for x² - px + q = 0:\nSum of roots: α + β = p\nProduct of roots: αβ = q\nWe know that (α - β)² = (α + β)² - 4αβ.\nSubstituting values: 1² = p² - 4q\n=> 1 = p² - 4q\n=> p² = 4q + 1.\nHence Option A is correct.",
                "चरणबद्ध हल:\nमाना मूल α और β हैं। दिया है: |α - β| = 1.\nमूलों का योग: α + β = p तथा गुणनफल: αβ = q.\nसूत्र: (α - β)² = (α + β)² - 4αβ\n1 = p² - 4q => p² = 4q + 1. अतः विकल्प A सही है।"
            ),
            (
                p1_id, "NDA", "Mathematics", "Calculus & Derivatives", "Hard",
                "What is the derivative of f(x) = ln(sec x + tan x) with respect to x?",
                "x के सापेक्ष f(x) = ln(sec x + tan x) का अवकलन (derivative) क्या है?",
                "sec x", "sec x",
                "tan x", "tan x",
                "sec x tan x", "sec x tan x",
                "sec² x", "sec² x",
                "A",
                "Step-by-step Solution:\nUsing the chain rule of differentiation:\nd/dx [ln(u)] = (1/u) * du/dx.\nHere u = sec x + tan x.\ndu/dx = sec x tan x + sec² x = sec x (tan x + sec x).\nTherefore:\nd/dx [ln(sec x + tan x)] = [sec x (sec x + tan x)] / (sec x + tan x) = sec x.\nHence, the correct option is A.",
                "चरणबद्ध हल:\nचेन नियम से:\nd/dx [ln(sec x + tan x)] = 1/(sec x + tan x) * (sec x tan x + sec² x)\n= [sec x (tan x + sec x)] / (sec x + tan x) = sec x.\nअतः विकल्प A सही उत्तर है।"
            ),
            (
                p1_id, "NDA", "Mathematics", "Matrices & Determinants", "Moderate",
                "If A is a square matrix of order 3 such that |A| = 4, then what is the value of |adj(A)|?",
                "यदि A कोटि 3 का एक वर्ग आव्यूह (square matrix) है जिसमें |A| = 4 है, तो |adj(A)| का मान क्या होगा?",
                "4", "4",
                "16", "16",
                "64", "64",
                "12", "12",
                "B",
                "Step-by-step Solution:\nFor any square matrix A of order n:\n|adj(A)| = |A|^(n - 1).\nHere order n = 3 and determinant |A| = 4.\nTherefore:\n|adj(A)| = 4^(3 - 1) = 4² = 16.\nHence Option B is correct.",
                "चरणबद्ध हल:\nप्रमेय अनुसार, कोटि n वाले आव्यूह A के लिए: |adj(A)| = |A|^(n - 1).\nयहाँ n = 3 और |A| = 4 है।\nअतः |adj(A)| = 4^(3 - 1) = 4² = 16. विकल्प B सही है।"
            ),
            (
                p1_id, "NDA", "Mathematics", "Vectors & 3D Geometry", "Moderate",
                "What is the angle between the two unit vectors â and b̂ if |â + b̂| = √3?",
                "यदि दो मात्रक सदिशों â और b̂ के लिए |â + b̂| = √3 है, तो उनके बीच का कोण क्या है?",
                "30° (π/6)", "30° (π/6)",
                "45° (π/4)", "45° (π/4)",
                "60° (π/3)", "60° (π/3)",
                "90° (π/2)", "90° (π/2)",
                "C",
                "Step-by-step Solution:\n|â + b̂|² = |â|² + |b̂|² + 2(â · b̂)\nSince â and b̂ are unit vectors: |â| = 1, |b̂| = 1.\nAlso, â · b̂ = |â||b̂| cos θ = 1 * 1 * cos θ = cos θ.\nGiven: |â + b̂| = √3 => |â + b̂|² = 3.\nTherefore:\n3 = 1 + 1 + 2 cos θ\n3 = 2 + 2 cos θ\n2 cos θ = 1 => cos θ = 1/2.\nSince cos(60°) = 1/2, θ = 60° (or π/3 radians).\nHence Option C is correct.",
                "चरणबद्ध हल:\n|â + b̂|² = |â|² + |b̂|² + 2|â||b̂| cos θ\n3 = 1 + 1 + 2 cos θ => 2 cos θ = 1 => cos θ = 1/2 => θ = 60° (π/3).\nअतः विकल्प C सही है।"
            ),
            (
                p1_id, "NDA", "Mathematics", "Probability", "Moderate",
                "Two dice are thrown simultaneously. What is the probability that the sum of the numbers appearing on both dice is a prime number?",
                "दो पासे एक साथ फेंके जाते हैं। दोनों पासों पर आने वाली संख्याओं का योग एक अभाज्य संख्या (Prime Number) होने की प्रायिकता क्या है?",
                "5 / 12", "5 / 12",
                "7 / 18", "7 / 18",
                "1 / 2", "1 / 2",
                "11 / 36", "11 / 36",
                "A",
                "Step-by-step Solution:\nTotal sample space when 2 dice are rolled = 6 * 6 = 36 outcomes.\nPossible prime sums between 2 and 12 are: 2, 3, 5, 7, 11.\nOutcomes giving sum = 2: (1,1) -> 1\nOutcomes giving sum = 3: (1,2), (2,1) -> 2\nOutcomes giving sum = 5: (1,4), (2,3), (3,2), (4,1) -> 4\nOutcomes giving sum = 7: (1,6), (2,5), (3,4), (4,3), (5,2), (6,1) -> 6\nOutcomes giving sum = 11: (5,6), (6,5) -> 2\nTotal favourable outcomes = 1 + 2 + 4 + 6 + 2 = 15.\nProbability = 15 / 36 = 5 / 12.\nOption A is correct.",
                "चरणबद्ध हल:\nकुल परिणाम = 36.\nअभाज्य योग संभव हैं: 2, 3, 5, 7, 11.\nअनुकूल परिणाम = 1 + 2 + 4 + 6 + 2 = 15.\nप्रायिकता = 15/36 = 5/12. विकल्प A सही उत्तर है।"
            ),

            # Paper 2: NDA General Ability Test (GAT)
            (
                p2_id, "NDA", "General Ability", "Indian Polity & Constitution", "Moderate",
                "Which Article of the Constitution of India provides for the Supreme Command of the Defence Forces of the Union to be vested in the President?",
                "भारत के संविधान का कौन सा अनुच्छेद यह प्रावधान करता है कि संघ के रक्षा बलों का सर्वोच्च समादेश राष्ट्रपति में निहित होगा?",
                "Article 52", "अनुच्छेद 52",
                "Article 53(2)", "अनुच्छेद 53(2)",
                "Article 72", "अनुच्छेद 72",
                "Article 352", "अनुच्छेद 352",
                "B",
                "Detailed Explanation:\nArticle 53(2) of the Indian Constitution states: 'Without prejudice to the generality of the foregoing provision, the supreme command of the Defence Forces of the Union shall be vested in the President and the exercise thereof shall be regulated by law.'\nArticle 52 simply declares 'There shall be a President of India'.\nArticle 72 confers pardoning powers.\nArticle 352 deals with National Emergency.\nTherefore, Option B is correct.",
                "विस्तृत व्याख्या:\nभारतीय संविधान का अनुच्छेद 53(2) स्पष्ट रूप से कहता है कि संघ के रक्षा बलों का सर्वोच्च समादेश राष्ट्रपति में निहित होगा और उसका प्रयोग विधि द्वारा विनियमित होगा। अतः विकल्प B सही है।"
            ),
            (
                p2_id, "NDA", "General Ability", "Defence & Military History", "Moderate",
                "Where is the headquarters of the Eastern Naval Command of the Indian Navy located?",
                "भारतीय नौसेना के पूर्वी नौसेना कमान (Eastern Naval Command) का मुख्यालय कहाँ स्थित है?",
                "Kolkata", "कोलकाता",
                "Visakhapatnam", "विशाखापत्तनम",
                "Chennai", "चेन्नई",
                "Port Blair", "पोर्ट ब्लेयर",
                "B",
                "Detailed Explanation:\nThe Indian Navy operates three operational commands:\n1. Western Naval Command: Mumbai (Headquarters)\n2. Eastern Naval Command: Visakhapatnam (Headquarters)\n3. Southern Naval Command: Kochi (Training Command)\nNote: Port Blair is the headquarters of India's first unified tri-service command, the Andaman & Nicobar Command (ANC).\nTherefore, Eastern Naval Command is headquartered in Visakhapatnam (Option B).",
                "विस्तृत व्याख्या:\nभारतीय नौसेना की तीन परिचालन कमानें हैं:\n1. पश्चिमी नौसेना कमान: मुंबई\n2. पूर्वी नौसेना कमान: विशाखापत्तनम\n3. दक्षिणी नौसेना कमान: कोच्चि (प्रशिक्षण कमान)\nपोर्ट ब्लेयर अंडमान और निकोबार कमान (त्रि-सेवा) का मुख्यालय है। अतः विकल्प B सही है।"
            ),
            (
                p2_id, "NDA", "General Ability", "Physics & Modern Science", "Moderate",
                "A bullet of mass m moving with velocity v strikes a stationary wooden block of mass M and gets embedded in it. What is the common velocity of the combined system after the impact?",
                "v वेग से गतिशील m द्रव्यमान की एक गोली M द्रव्यमान के एक स्थिर लकड़ी के गुटके से टकराकर उसमें धंस जाती है। संघट्ट के बाद संयुक्त निकाय का उभयनिष्ठ वेग क्या होगा?",
                "v * m / (M + m)", "v * m / (M + m)",
                "v * M / (M + m)", "v * M / (M + m)",
                "v * (M + m) / m", "v * (M + m) / m",
                "v / 2", "v / 2",
                "A",
                "Step-by-step Solution:\nThis is a case of a completely inelastic collision.\nBy the Law of Conservation of Linear Momentum:\nTotal initial momentum = Total final momentum\nInitial Momentum = m * v + M * 0 = mv\nFinal Momentum = (m + M) * V_common\nEquating both:\nmv = (m + M) * V_common\n=> V_common = mv / (M + m).\nHence, Option A is correct.",
                "चरणबद्ध हल:\nरैखिक संवेग संरक्षण के नियम से:\nप्रारंभिक संवेग = अंतिम संवेग\nm * v + M * 0 = (m + M) * V\nV = m*v / (m + M).\nअतः विकल्प A सही उत्तर है।"
            ),
            (
                p2_id, "NDA", "General Ability", "English Vocabulary", "Moderate",
                "Select the word that is most nearly SYNONYMOUS with the capitalized word:\n'The commander gave an UNEQUIVOCAL order to advance.'",
                "बड़े अक्षरों में लिखे शब्द का सबसे निकटतम पर्यायवाची (SYNONYM) चुनें:\n'The commander gave an UNEQUIVOCAL order to advance.'",
                "Ambiguous", "Ambiguous",
                "Explicit and clear", "Explicit and clear",
                "Hesitant", "Hesitant",
                "Temporary", "Temporary",
                "B",
                "Detailed Explanation:\n'Unequivocal' means leaving no doubt, unambiguous, unmistakable, clear and direct.\n- Ambiguous means open to more than one interpretation (opposite).\n- Hesitant means tentative or reluctant.\n- Explicit and clear is the exact synonym.\nTherefore, Option B is correct.",
                "विस्तृत व्याख्या:\n'Unequivocal' का अर्थ स्पष्ट, अकाट्य और असंदिग्ध होता है। इसका सही पर्यायवाची 'Explicit and clear' है। विकल्प B सही है।"
            ),

            # Paper 4: Indian Army Agniveer GD
            (
                p4_id, "AGNIVEER_ARMY_GD", "General Knowledge", "Indian History & Heritage", "Easy",
                "Who was the first recipient of the Param Vir Chakra, India's highest military decoration?",
                "भारत के सर्वोच्च सैन्य अलंकरण 'परमवीर चक्र' के प्रथम प्राप्तकर्ता कौन थे?",
                "Major Somnath Sharma", "मेजर सोमनाथ शर्मा",
                "Captain Vikram Batra", "कैप्टन विक्रम बत्रा",
                "Subedar Major Bana Singh", "सूबेदार मेजर बाना सिंह",
                "Lance Naik Albert Ekka", "लांस नायक अल्बर्ट एक्का",
                "A",
                "Detailed Explanation:\nMajor Somnath Sharma of the 4th Battalion, Kumaon Regiment was posthumously awarded India's first Param Vir Chakra for his supreme gallantry during the Battle of Badgam in Jammu & Kashmir on 3 November 1947.\nCaptain Vikram Batra received PVC posthumously in the 1999 Kargil War.\nSubedar Major Bana Singh received PVC for Operation Rajiv at Siachen Glacier in 1987.\nOption A is correct.",
                "विस्तृत व्याख्या:\n4 कुमाऊं रेजिमेंट के मेजर सोमनाथ शर्मा 3 नवंबर 1947 को बड़गाम के युद्ध में अदम्य साहस दिखाते हुए वीरगति को प्राप्त हुए और उन्हें मरणोपरांत भारत का प्रथम परमवीर चक्र प्रदान किया गया। विकल्प A सही है।"
            ),
            (
                p4_id, "AGNIVEER_ARMY_GD", "Mathematics", "Percentage", "Moderate",
                "If the price of diesel increases by 25%, by what percentage must a transport operator reduce its consumption so that the overall expenditure remains unchanged?",
                "यदि डीजल की कीमत में 25% की वृद्धि हो जाती है, तो एक ट्रांसपोर्ट ऑपरेटर को अपनी खपत में कितने प्रतिशत की कमी करनी चाहिए ताकि कुल खर्च अपरिवर्तित रहे?",
                "20%", "20%",
                "25%", "25%",
                "16.67%", "16.67%",
                "30%", "30%",
                "A",
                "Step-by-step Solution:\nLet initial price = Rs. 100 per unit, and initial consumption = 100 units.\nInitial Expenditure = 100 * 100 = Rs. 10,000.\nNew price = 100 + 25% = Rs. 125.\nTo keep expenditure at Rs. 10,000, new consumption = 10,000 / 125 = 80 units.\nReduction in consumption = 100 - 80 = 20 units.\nPercentage reduction = (20 / 100) * 100 = 20%.\nFormula shortcut: [r / (100 + r)] * 100 = [25 / 125] * 100 = 20%.\nTherefore, Option A is correct.",
                "चरणबद्ध हल:\nसूत्र: खपत में कमी % = [r / (100 + r)] * 100\n= [25 / (100 + 25)] * 100 = [25 / 125] * 100 = 20%.\nअतः खर्च अपरिवर्तित रखने के लिए खपत में 20% की कटौती करनी होगी। विकल्प A सही है।"
            ),
            (
                p4_id, "AGNIVEER_ARMY_GD", "General Science", "Human Biology & Physiology", "Easy",
                "Which blood group is known as the Universal Donor?",
                "किस रक्त समूह (Blood Group) को 'सर्वदाता' कहा जाता है?",
                "Group AB+", "ग्रुप AB+",
                "Group O-", "ग्रुप O-",
                "Group A+", "ग्रुप A+",
                "Group B-", "ग्रुप B-",
                "B",
                "Detailed Explanation:\nBlood group O- (O negative) lacks A, B antigens and the Rh factor on the surface of its red blood cells, which means it will not trigger an immune response in recipients of any other blood type. Hence O- is the true Universal Donor.\nGroup AB+ is the Universal Recipient.\nOption B is correct.",
                "विस्तृत व्याख्या:\nरक्त समूह O negative (O-) में लाल रक्त कोशिकाओं पर A या B एंटीजन तथा Rh कारक नहीं पाया जाता, इसलिए इसे किसी भी रक्त समूह वाले व्यक्ति को सुरक्षित रूप से दिया जा सकता है। यह 'सर्वदाता' कहलाता है। विकल्प B सही है।"
            ),
            (
                p4_id, "AGNIVEER_ARMY_GD", "Logical Reasoning", "Number Series", "Moderate",
                "Identify the next number in the given series: 7, 14, 28, 56, 112, ?",
                "दी गई श्रृंखला में अगला पद ज्ञात कीजिए: 7, 14, 28, 56, 112, ?",
                "168", "168",
                "224", "224",
                "212", "212",
                "240", "240",
                "B",
                "Step-by-step Solution:\nExamine the multiplier between consecutive terms:\n7 * 2 = 14\n14 * 2 = 28\n28 * 2 = 56\n56 * 2 = 112\n112 * 2 = 224.\nEach term is doubled to get the next term.\nTherefore, the missing number is 224 (Option B).",
                "चरणबद्ध हल:\nश्रृंखला में प्रत्येक पद को 2 से गुणा किया जा रहा है:\n7 × 2 = 14\n14 × 2 = 28\n28 × 2 = 56\n56 × 2 = 112\n112 × 2 = 224. अतः विकल्प B सही है।"
            ),

            # Paper 5: AFCAT Practice Set
            (
                p5_id, "AFCAT", "Reasoning & Aptitude", "Military Aptitude & Analogies", "Moderate",
                "Complete the analogy:\nRadar : Radio Waves :: Sonar : ?",
                "सादृश्यता पूर्ण कीजिए:\nरडार : रेडियो तरंगें :: सोनार : ?",
                "Sound Waves (Ultrasonic)", "ध्वनि तरंगें (पराश्रव्य)",
                "Light Waves", "प्रकाश तरंगें",
                "Microwaves", "माइक्रोवेव",
                "Infrared Rays", "अवरक्त किरणें",
                "A",
                "Detailed Explanation:\nRADAR (Radio Detection and Ranging) utilizes radio electromagnetic waves to detect objects in the air.\nSONAR (Sound Navigation and Ranging) utilizes acoustic/sound waves (typically ultrasonic frequencies) to navigate and detect submerged submarines and underwater obstacles.\nHence, Option A is correct.",
                "विस्तृत व्याख्या:\nRADAR रेडियो तरंगों का उपयोग वायु में वस्तुओं का पता लगाने के लिए करता है। जबकि SONAR जल के भीतर वस्तुओं और पनडुब्बियों का पता लगाने के लिए ध्वनि तरंगों (पराश्रव्य तरंगों) का उपयोग करता है। अतः विकल्प A सही है।"
            ),
            (
                p5_id, "AFCAT", "General Awareness", "Defence Knowledge", "Moderate",
                "Which supersonic cruise missile was developed as a joint venture between India (DRDO) and Russia (NPOM)?",
                "भारत (DRDO) और रूस (NPOM) के संयुक्त उद्यम द्वारा किस सुपरसोनिक क्रूज मिसाइल का विकास किया गया?",
                "Agni-V", "अग्नि-V",
                "BrahMos", "ब्रह्मोस",
                "Prithvi-II", "पृथ्वी-II",
                "Astra", "अस्त्र",
                "B",
                "Detailed Explanation:\nBrahMos is named after two sacred rivers: the Brahmaputra of India and the Moskva of Russia. It is the world's fastest supersonic cruise missile with speeds reaching Mach 2.8 to 3.0, capable of launch from submarines, ships, aircraft, or land.\nAgni and Prithvi are indigenous Indian ballistic missiles.\nOption B is correct.",
                "विस्तृत व्याख्या:\nब्रह्मोस (BrahMos) भारत की ब्रह्मपुत्र और रूस की मोस्कवा नदी के नाम पर रखा गया एक संयुक्त उद्यम है। यह विश्व की सबसे तेज गति वाली सुपरसोनिक क्रूज मिसाइल है। अतः विकल्प B सही है।"
            )
        ]

        for q in questions_list:
            cursor.execute('''
            INSERT INTO questions (
                paper_id, exam_code, subject, topic, difficulty,
                question_text_en, question_text_hi,
                option_a_en, option_a_hi,
                option_b_en, option_b_hi,
                option_c_en, option_c_hi,
                option_d_en, option_d_hi,
                correct_option, explanation_en, explanation_hi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', q)

    # Seed Aspirant Test Attempt (so aspirant has realistic weakness analysis from real test data!)
    cursor.execute("SELECT COUNT(*) FROM test_attempts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id FROM users WHERE username = 'aspirant'")
        student_row = cursor.fetchone()
        cursor.execute("SELECT id FROM test_papers WHERE exam_code = 'AGNIVEER_ARMY_GD'")
        paper_row = cursor.fetchone()

        if student_row and paper_row:
            s_id = student_row['id']
            p_id = paper_row['id']
            # Realistic attempt: 4 questions attempted:
            # Q1 (Param Vir Chakra): Correct
            # Q2 (Percentage): Wrong (picked B instead of A) -> weak in Percentage!
            # Q3 (Blood group O-): Correct
            # Q4 (Number series): Correct
            sample_responses = {
                "q_history": {"selected": "A", "correct": "A", "topic": "Indian History & Heritage", "subject": "General Knowledge", "is_correct": True, "time": 42},
                "q_percentage": {"selected": "B", "correct": "A", "topic": "Percentage", "subject": "Mathematics", "is_correct": False, "time": 95},
                "q_biology": {"selected": "B", "correct": "B", "topic": "Human Biology & Physiology", "subject": "General Science", "is_correct": True, "time": 35},
                "q_series": {"selected": "B", "correct": "B", "topic": "Number Series", "subject": "Logical Reasoning", "is_correct": True, "time": 50}
            }
            topic_stats = {
                "Percentage": {"total": 1, "correct": 0, "accuracy": 0.0, "status": "Needs Improvement", "subject": "Mathematics"},
                "Indian History & Heritage": {"total": 1, "correct": 1, "accuracy": 100.0, "status": "Strong Performance", "subject": "General Knowledge"},
                "Human Biology & Physiology": {"total": 1, "correct": 1, "accuracy": 100.0, "status": "Strong Performance", "subject": "General Science"},
                "Number Series": {"total": 1, "correct": 1, "accuracy": 100.0, "status": "Strong Performance", "subject": "Logical Reasoning"}
            }
            cursor.execute('''
            INSERT INTO test_attempts (
                user_id, paper_id, score, max_marks, total_questions,
                correct_count, incorrect_count, unattempted_count, accuracy_percent,
                time_taken_seconds, responses_json, topic_stats_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                s_id, p_id, 5.5, 8.0, 4,
                3, 1, 0, 75.0, 222,
                json.dumps(sample_responses), json.dumps(topic_stats)
            ))

    # Seed Applications in Tracker for Aspirant
    cursor.execute("SELECT COUNT(*) FROM application_tracker")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id FROM users WHERE username = 'aspirant'")
        u_row = cursor.fetchone()
        if u_row:
            apps = [
                (u_row['id'], "UPSC NDA & NA (I) 2026", "Union Public Service Commission", "2026-10-08", "Application Submitted", "2027-04-18", "Not Released", "NDA2026/89412", "Targeting Army Wing IMA. Preparation in full swing. Completed Maths syllabus."),
                (u_row['id'], "Indian Army Agniveer GD Rally", "Indian Army HQ Recruiting Zone", "2026-09-28", "Admit Card Available", "2026-12-10", "Available for Download", "IA/AGN/2026/41092", "Morning 5 Km run timing achieved: 22 mins. Need to sharpen 10 pull-ups."),
                (u_row['id'], "SSC GD Constable 2026-27", "Staff Selection Commission", "2026-09-10", "Fee Paid", "2027-01-15", "Expected Dec 2026", "SSC2026GD7712", "Applied for CISF & BSF preferences.")
            ]
            for a in apps:
                cursor.execute('''
                INSERT INTO application_tracker (
                    user_id, exam_name, organization, application_date, status,
                    exam_date, admit_card_status, reference_number, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', a)

    # Seed Study Planner
    cursor.execute("SELECT COUNT(*) FROM study_planner")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id FROM users WHERE username = 'aspirant'")
        u_row = cursor.fetchone()
        if u_row:
            tasks = [
                (u_row['id'], "Solve 50 Trigonometry PYQs from NDA 2020-2024", "Mathematics", "2026-10-18", "High", 1),
                (u_row['id'], "Revise Articles 52-78 of Indian Constitution & Military Powers", "Polity", "2026-10-20", "Medium", 0),
                (u_row['id'], "Practice 1.6 Km timed running (Target under 5m 30s)", "Physical Fitness", "2026-10-16", "High", 0),
                (u_row['id'], "Attempt Full Length NDA Mock Test 02 on Defence Path", "Full Mock", "2026-10-22", "High", 0)
            ]
            for t in tasks:
                cursor.execute('''
                INSERT INTO study_planner (user_id, title, subject, target_date, priority, is_completed)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', t)

    # Seed Saved Jobs for Aspirant
    cursor.execute("SELECT COUNT(*) FROM saved_jobs")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id FROM users WHERE username = 'aspirant'")
        u_row = cursor.fetchone()
        if u_row:
            cursor.execute("SELECT id FROM recruitments LIMIT 2")
            for r_rec in cursor.fetchall():
                cursor.execute("INSERT OR IGNORE INTO saved_jobs (user_id, recruitment_id) VALUES (?, ?)", (u_row['id'], r_rec['id']))

    # Seed Announcements
    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        ann = [
            ("UPSC NDA & NA (I) 2026 Online Application Open", "Recruitment", "Eligible 10+2 aspirants can submit online forms on upsc.gov.in before the closing date. Verify age criteria carefully."),
            ("New Authentic 2024 PYQ Papers Uploaded", "Academic", "NDA & CDS 2024 authentic Previous Year Question papers with step-by-step mathematical solutions are now live in the PYQ Library."),
            ("Defence Path Multi-Language Feature Live", "Platform", "Aspirants across India can now experience Defence Path in 13 Indian languages including Hindi, English, Bengali, Tamil, Telugu, and Urdu.")
        ]
        for a in ann:
            cursor.execute("INSERT INTO announcements (title, category, content) VALUES (?, ?, ?)", a)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("Initializing DEFENCE PATH Database...")
    init_db()
    seed_data()
    print("Database initialization and seeding completed successfully!")

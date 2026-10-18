# DEFENCE PATH
> **"Your Dream. Your Discipline. Your Uniform."**

A modern, full-stack digital platform engineered for Indian defence aspirants across the **Indian Army, Indian Navy, Indian Air Force, Indian Coast Guard, and Central Armed Police Forces (BSF, CRPF, CISF, ITBP, SSB, Assam Rifles)**.

---

### Project Developer & System Architect
* **Lead Developer:** **Er. Prashant Mishra**
* **Project Role:** Full-Stack System Architect & Developer – DEFENCE PATH
* **Contact Phone Hotline:** **6390314464**
* **Official Email:** *Configurable in Admin Profile (currently displays: "Developer email will be available soon.")*

---

## 1. Key Capabilities & Platform Modules

1. **Latest Defence Recruitment Notices (Gazette-Synchronized):**
   - Active notifications across Army, Navy, Air Force, Coast Guard & CAPF.
   - Status indicators: *Currently Open, Closing Soon, Upcoming, Application Closed, Admit Card Released*.
   - Filter by Organization, Qualification, Age Bracket, and Application Status.
   - Verified direct links to official recruitment portals.

2. **Official Recruitment Portals Directory:**
   - Centralized gateway for `joinindianarmy.nic.in`, `joinindiannavy.gov.in`, `careerindianairforce.cdac.in`, `upsc.gov.in`, `ssc.gov.in`, and CAPF portals.
   - Verified dates and official statutory disclaimers.

3. **Interactive Exam Eligibility Checker:**
   - Evaluates Date of Birth, Academic Streams (10th, 12th PCM/Other, Graduation, B.Tech), Social Categories (General, OBC, SC, ST), Gender, and Physical Standards against Gazetted rules.
   - Calculates exact age as of official cutoff dates and applies authorized category relaxations.
   - Returns itemized PASS / FAIL audit checklists with physical standard requirements.

4. **Authentic Previous Year Question (PYQ) Library:**
   - Authentic past papers for UPSC NDA, CDS, AFCAT, Army Agniveer GD/Tech, Navy SSR, and SSC GD.
   - Subject-wise and topic-wise categorization.
   - Dynamic **PDF Generator** using ReportLab for offline paper download.
   - Interactive Study Mode with detailed step-by-step mathematical explanations.

5. **Professional Online CBT Examination Engine:**
   - Realistic Computer-Based Test (CBT) interface.
   - Live countdown timer with auto-submission on timeout.
   - 5-state Question Palette (*Answered, Not Answered, Not Visited, Marked for Review, Marked & Answered*).
   - Real-time scoring using official examination marking schemes (e.g., +4 / -1.33 for NDA, +1 / -0.33 for CDS, +2 / -0.5 for Agniveer GD).
   - Bilingual question view toggle (English & Hindi).
   - Client-side session recovery to prevent data loss on browser refresh.

6. **Weakness Analysis & Performance Diagnostics:**
   - Calculates topic-wise and subject-wise accuracy from persistent test attempts.
   - Transparent rule-based classification:
     - **Needs Improvement** (< 50% accuracy)
     - **Practice Recommended** (50% – 70% accuracy)
     - **Strong Performance** (> 70% accuracy)
   - Interactive charts for subject benchmarking and score progression over time.

7. **Aspirant Command Dossier (Student Dashboard):**
   - Personal dashboard tracking tests, accuracy %, test history, and study streak.
   - **Application Tracker:** Privately record examination applications, roll numbers, exam dates, admit card updates, and preparation logs.
   - **Strategic Study Planner:** Daily milestone scheduler with completion toggles and priority tagging.
   - **Saved Job Notices:** One-click notice bookmarking.

8. **Protected Administrator Command Centre:**
   - Recruitment Manager (CRUD for job notices, PDF links, deadlines).
   - PYQ & Question Bank Manager (Add papers, add questions with rich step-by-step solutions).
   - Broadcast System Announcements to homepage ticker.
   - Registered Cadre / User Management.
   - **Editable Developer Profile:** Er. Prashant Mishra profile editor with photo upload/preview, bio, contact number, and links directly synced with the database.

9. **Global 13-Language Internationalization (i18n):**
   - Supports: **English, Hindi, Bengali, Marathi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Odia, Assamese, and Urdu (with RTL layout)**.

---

---

## 2. How to Run Locally

### Prerequisites:
- Python 3.10+ (Tested on Python 3.14)
- Flask, Pillow, ReportLab, Werkzeug

### Run Command:
```powershell
python run.py
```

The portal will start on:
```
http://127.0.0.1:5000
```

---

## 3. Legal & Regulatory Compliance Notice

> **Disclaimer:** Defence Path is an independent educational platform engineered for defence aspirant preparation and examination intelligence. It is not affiliated with the Government of India, the Ministry of Defence, or any armed forces recruitment board. All applications must be submitted directly through official recruitment websites.

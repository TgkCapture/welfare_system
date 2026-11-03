# Mzugoss Welfare Contribution System

A Flask-based system to automate the tracking of monthly contributions, simplify reporting, and streamline operations for welfare groups like Mzugoss. This solution is scalable for any welfare group managing member contributions through Excel or Google Sheets.

---

## 📊 Key Features

* **Excel/Google Sheets Integration**
  Upload Excel files or connect to Google Sheets to import member contribution data.

* **Automated Reporting**
  - **Comprehensive PDF Reports**: Detailed reports showing all financial data including:
    - Total contributions
    - Money dispensed
    - Book balance
    - List of paid members
    - Defaulters list
  - **Quick-view PNG Reports**: Condensed image showing only paid members and key financials

* **Version Control for Developers**
  - Uses `bump2version==1.0.1` for seamless version management
  - Standardized version bumping (major.minor.patch)

* **User Management**
  Simple login system for members and admins to securely access and download reports.

* **Multi-Group Support**
  Each welfare group can upload their own dataset and manage reports independently.

* **Clean UI**
  Friendly and responsive web dashboard for selecting, filtering, viewing, and downloading reports.

---

## ⚖️ Technology Stack

| Layer                   | Technology         |
| ----------------------- | ------------------ |
| Backend                 | Flask (Python)     |
| Data Processing         | pandas             |
| PDF Report Generation   | reportlab          |
| PNG/Charts              | matplotlib, Pillow |
| Spreadsheet Integration | openpyxl, gspread  |
| Version Control         | bump2version       |
| Auth & Storage          | SQLite (built-in)  |

---

## ⚡ Installation

### 1. Clone the Repo

```bash
git clone https://github.com/tgkcapture/welfare_system.git
cd welfare_system
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install Requirements

```bash
pip install -r requirements.txt
```

### 4. Set Up the Database

The schema is managed with Flask-Migrate.

```bash
export FLASK_APP=run.py          # Windows PowerShell: $env:FLASK_APP = "run.py"
flask db upgrade                 # create or update the database
flask create-superadmin          # platform operator account (no group)
flask create-group               # a welfare group, with preset roles
flask create-admin --group <slug>   # the group's first officer (Chairperson)
```

Only `create-superadmin` is required. After that, the superadmin can create
groups and their first officers at `/platform/` in the browser. Officers who
can manage officers edit their group's roles at `/admin/roles`.

Each group's files are kept in `uploads/<slug>/` and `reports/<slug>/`.
When upgrading from a version without group folders, run once:

```bash
flask move-files-to-groups --dry-run   # preview
flask move-files-to-groups
```

Report files expire after the group's retention period (set on its Settings
page, otherwise `REPORT_RETENTION_DAYS`). Expired reports are archived, not
deleted. `flask cleanup-files [--group <slug>] [--dry-run]` runs cleanup by hand.

The daily cleanup runs at `CLEANUP_TIME` (default `02:00`) in every worker
process; the first one to claim the day in the database does the work and
the others skip it, so any number of workers or servers is safe. To use cron
instead, set `ENABLE_AUTO_CLEANUP=false` and run `flask daily-cleanup` once a
day; it also runs at most once a day.

Upgrading an existing single-group install automatically creates a
"Mzugoss" group (slug `mzugoss`) and moves existing users and reports into
it: admins become Chairperson, clerks become Treasurer, and viewer
accounts are deactivated.

Signing in:

* Officers: `/g/<slug>/login` (for example `/g/mzugoss/login`)
* Platform superadmins: `/platform/login`
* `/auth/login` asks for the group code and remembers it for next time

Failed attempts are rate limited per IP; successful ones never count, since
many members can share one mobile network address:

* wrong passwords (sign-in and password change) and unknown group codes:
  `LOGIN_RATE_LIMIT`, default `10 per minute;50 per hour`
* wrong access codes, PINs and personal history links:
  `PUBLIC_LOOKUP_RATE_LIMIT`, default `10 per minute;30 per hour`

With several workers, point `RATELIMIT_STORAGE_URI` at a shared store such
as Redis; otherwise each worker counts on its own. Behind a reverse proxy
(nginx, a load balancer), set `TRUSTED_PROXIES` to the number of proxies so
limits and the audit log see each visitor's own address. Leave it at `0`
when the app is reached directly, because the forwarded headers can be forged.

If you already have a database created by an older version (before
migrations were added), mark it as up to date once instead of upgrading:

```bash
flask db stamp 365dc0d4aa41
```

### 5. Run the App

```bash
python run.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🔧 Usage Guide

### For Administrators:

1. **Upload Sheet**: 
   - Go to homepage and upload your group's Excel file
   - System automatically extracts:
     - Member names
     - Monthly contributions
     - Money dispensed
     - Total book balance

2. **Dashboard**: 
   - Select year/month to generate report
   - View key statistics at a glance

3. **Generate Reports**:
   - **PDF Report**: Comprehensive document with all financial details
   - **PNG Report**: Quick-view image showing only paid members

4. **Download & Share**: 
   - Save reports in preferred format
   - Distribute to group members

### For Developers:

```bash
# Tests
pip install -r requirements-dev.txt
pytest

# Schema changes: edit the models, then generate and review a migration
flask db migrate -m "describe the change"
flask db upgrade
```

Styles are Tailwind, written in `app/static/src/app.css` and shared Jinja
macros (`app/templates/components/ui.html`). The built `app/static/css/app.css`
is committed, so running the app never needs Node. To change styles:

```bash
npm install            # once
npm run build:css      # or: npm run watch:css while editing
```

Commit the rebuilt `app/static/css/app.css` with your template changes.

```bash
# Version management (using bump2version)
bump2version patch  # for bug fixes
bump2version minor  # for new features
bump2version major  # for breaking changes
```

---

## 📅 Excel Format Requirements

Ensure your file follows this pattern:

* **Sheet naming**: Year (e.g., `2025`)
* **Columns**: 
  - `Name` 
  - `January` 
  - `February` 
  - ... 
  - `December`
* **Special Rows**:
  - `MONEY DISPENSED` (single value)
  - `TOTAL BOOK BALANCE` (single value)
* **Amounts**: Should be numeric (e.g., 500, 1000)

---

## ✅ Achieved Milestones

1. **Data Extraction**: Successfully extracts from Excel:
   - Member contributions
   - Financial summaries
   - Payment status

2. **Report Generation**:
   - Comprehensive PDF reports with all financial details
   - Condensed PNG images showing paid members

3. **User Workflow**:
   - Simple file upload
   - Intuitive report selection
   - One-click generation of both report types

---

## 👤 User Roles

* **Admin**: Can upload files, manage reports, access all data
* **Member**: Can view and download reports for their group

---

## 🚀 Future Improvements

* Email notifications for members
* Payment tracking and reminders
* Charts and analytics dashboard
* Export to CSV/Excel

---

## 🌟 Credits

Built with ❤️ by @tgkcapture. Designed for the community.

---


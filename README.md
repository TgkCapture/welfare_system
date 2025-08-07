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
cd mzugoss-welfare
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

### 4. Run the App

```bash
python app.py
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


# Mzugoss Welfare Contribution System

A Flask-based system to automate the tracking of monthly contributions, simplify reporting, and streamline operations for welfare groups like Mzugoss. This solution is scalable for any welfare group managing member contributions through Excel or Google Sheets.

---

## 📊 Key Features

* **Excel/Google Sheets Integration**
  Upload Excel files or connect to Google Sheets to import member contribution data.

* **Automated Reporting**
  Generate PDF or PNG reports for any month or year, showing contributors and totals.

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

1. **Upload Sheet**: Go to homepage and upload your group's Excel file.
2. **Dashboard**: Choose the year/month to generate a report.
3. **Generate Report**: Click to generate PDF or PNG version.
4. **Download & Share**: Save and share the reports as needed.

---

## 📅 Excel Format

Ensure your file follows this pattern:

* Sheet name: Year (e.g., `2025`)
* Columns: `Name`, `January`, `February`, ..., `December`
* Amounts should be numeric (e.g., 500, 1000)

---

## 👤 User Roles

* **Admin**: Can upload files, manage reports.
* **Member**: Can view and download reports.

---

## 🚀 Future Improvements

* Email notifications for members
* Payment tracking and reminders
* Charts and analytics dashboard
* Export to CSV/Excel

---

## 🌟 Credits

Built with ❤️ by @tgkcapture . Designed for the community.

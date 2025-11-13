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

* **Docker Containerization**
  - Complete Docker support for development and production
  - Consistent environments across all deployments
  - Easy scaling and deployment

* **Environment Configuration**
  - Secure configuration management using `.env` files
  - Separation of development and production settings

* **User Management**
  Simple login system for members and admins to securely access and download reports.

* **Multi-Group Support**
  Each welfare group can upload their own dataset and manage reports independently.

* **Clean UI**
  Friendly and responsive web dashboard for selecting, filtering, viewing, and downloading reports.

* **Version Control for Developers**
  - Uses `bump2version==1.0.1` for seamless version management
  - Standardized version bumping (major.minor.patch)

---

## ⚖️ Technology Stack

| Layer                   | Technology         |
| ----------------------- | ------------------ |
| Backend                 | Flask (Python)     |
| Data Processing         | pandas             |
| PDF Report Generation   | reportlab          |
| PNG/Charts              | matplotlib, Pillow |
| Spreadsheet Integration | openpyxl, gspread  |
| Containerization        | Docker & Docker Compose |
| Environment Management  | python-dotenv      |
| Auth & Storage          | SQLite (built-in)  |

---

## 🐳 Quick Start with Docker

### Prerequisites
- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)

### 1. Clone the Repo
```bash
git clone https://github.com/tgkcapture/welfare_system.git
cd welfare_system
```

### 2. Set up Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your configuration
```

### 3. Run with Docker Compose
```bash
# Development environment
docker-compose up --build
```

The application will be available at `http://localhost:5000`

---

## 🔧 Traditional Installation (Without Docker)

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

### 4. Set up Environment Variables
```bash
# Copy and configure environment file
cp .env.example .env
# Edit .env with your settings
```

### 5. Run the App
```bash
python run.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🚀 Production Deployment

### Production Deployment with Docker
```bash
# Set up production environment
cp .env.example .env.prod
# Edit .env.prod with production values

# Deploy
docker-compose -f docker-compose.prod.yml up --build -d
```

### Environment Variables
Create a `.env` file with the following variables:

```env
# Flask Configuration
SECRET_KEY=your-super-secret-key
FLASK_ENV=development

# Database
SQLALCHEMY_DATABASE_URI=sqlite:///db.sqlite3

# File Paths
UPLOAD_FOLDER=uploads
REPORT_FOLDER=reports

# Google Sheets Configuration
GOOGLE_CREDENTIALS_PATH=credentials/mzugoss-welfare-5dab294def1f.json
DEFAULT_SHEET_URL=your-google-sheet-url-here
```

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

# In Docker container:
docker-compose exec web bump2version patch
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

1. **Containerization**: Full Docker support for consistent deployments
2. **Secure Configuration**: Environment-based configuration management
3. **Data Extraction**: Successfully extracts from Excel:
   - Member contributions
   - Financial summaries
   - Payment status
4. **Report Generation**:
   - Comprehensive PDF reports with all financial details
   - Condensed PNG images showing paid members
5. **User Workflow**:
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
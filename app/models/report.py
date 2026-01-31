# app/models/report.py
from datetime import datetime
from app import db

class GeneratedReport(db.Model):
    """Model for storing generated reports"""
    __tablename__ = 'generated_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    report_type = db.Column(db.String(50), nullable=False, default='contributions')  # 'contributions', 'summary', etc.
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_size = db.Column(db.Integer)  # in bytes
    total_contributions = db.Column(db.Float, default=0.0)
    contributors_count = db.Column(db.Integer, default=0)
    defaulters_count = db.Column(db.Integer, default=0)
    money_dispensed = db.Column(db.Float)
    total_book_balance = db.Column(db.Float)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    
    # Relationships
    generator = db.relationship('User', backref=db.backref('generated_reports', lazy=True))
    
    def __repr__(self):
        return f'<GeneratedReport {self.month}/{self.year} by {self.generator.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'year': self.year,
            'report_type': self.report_type,
            'filename': self.filename,
            'file_path': self.file_path,
            'generated_by': self.generated_by,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'file_size': self.file_size,
            'total_contributions': self.total_contributions,
            'contributors_count': self.contributors_count,
            'defaulters_count': self.defaulters_count,
            'money_dispensed': self.money_dispensed,
            'total_book_balance': self.total_book_balance,
            'is_archived': self.is_archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'generator_name': self.generator.email if self.generator else None
        }

class ReportAccessLog(db.Model):
    """Log report access for auditing"""
    __tablename__ = 'report_access_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('generated_reports.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50))  # 'view', 'download', 'preview'
    
    # Relationships
    report = db.relationship('GeneratedReport', backref=db.backref('access_logs', lazy=True))
    user = db.relationship('User', backref=db.backref('report_accesses', lazy=True))
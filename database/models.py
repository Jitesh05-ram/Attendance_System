from flask_login import UserMixin
from datetime import datetime, UTC
from .db import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=True)
    password = db.Column(db.String(200), nullable=True)
    google_id = db.Column(db.String(150), unique=True, nullable=True)
    role = db.Column(db.String(20), nullable=False, default='teacher')
    first_login = db.Column(db.Boolean, nullable=False, default=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)  # Email verification status
    verification_token = db.Column(db.String(200), nullable=True)
    verification_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    
    # Relationships
    students = db.relationship('Student', backref='user', lazy=True)
    subjects = db.relationship('Subject', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(50), nullable=False)  # e.g., MJ5, OE, VSC
    name = db.Column(db.String(100), nullable=True)  # Optional, for display
    subjects = db.relationship('Subject', backref='category', lazy=True)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=True, default='📚')  # Emoji for subject
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    attendance_records = db.relationship('Attendance', backref='subject', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    admission_year = db.Column(db.Integer, nullable=False)  # 4-digit year like 2026
    email = db.Column(db.String(150), nullable=True)
    attendance_records = db.relationship('Attendance', backref='student', lazy=True)
    
    @property
    def current_academic_year(self):
        """Get the current academic year (starts in July, e.g., 2025-2026)."""
        from datetime import datetime
        today = datetime.today()
        if today.month >= 7:  # July to December
            return today.year
        else:  # January to June
            return today.year - 1
    
    @property
    def years_since_admission(self):
        """Calculate how many academic years since admission."""
        return self.current_academic_year - self.admission_year
    
    @property
    def current_year(self):
        """Get current year: FY, SY, TY, or '' if beyond third year."""
        years = self.years_since_admission
        if years == 0:
            return 'FY'
        elif years == 1:
            return 'SY'
        elif years == 2:
            return 'TY'
        else:
            return ''
    
    @property
    def class_name(self):
        """Generate class name like '26FYBSC'."""
        if not self.current_year:
            return f'{str(self.admission_year)[-2:]}BSC'
        return f'{str(self.admission_year)[-2:]}{self.current_year}BSC'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(UTC).date())
    status = db.Column(db.String(10), nullable=False)

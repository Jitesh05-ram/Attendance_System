from flask_login import UserMixin
from datetime import datetime
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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    students = db.relationship('Student', backref='user', lazy=True)
    attendance_records = db.relationship('Attendance', backref='user', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(10), nullable=False, default='FY')  # FY, SY, TY
    email = db.Column(db.String(150), nullable=True)
    attendance_records = db.relationship('Attendance', backref='student', lazy=True)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    status = db.Column(db.String(10), nullable=False)

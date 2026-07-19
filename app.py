from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io
import os
import secrets
import string
from config import Config
from database.db import db
from database.models import User, Student, Attendance

# Initialize Google Services (if credentials file exists)
google_services = None
if os.path.exists(Config.GOOGLE_SERVICE_ACCOUNT_KEY) and Config.GOOGLE_SPREADSHEET_ID:
    try:
        from google_services import GoogleServices
        google_services = GoogleServices(
            Config.GOOGLE_SERVICE_ACCOUNT_KEY,
            Config.GOOGLE_SPREADSHEET_ID
        )
        print("Google Services initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize Google Services: {e}")

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
mail = Mail(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper function to generate random password
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(chars) for _ in range(length))

# Helper function to generate verification token
def generate_verification_token():
    return secrets.token_urlsafe(32)

# Helper function to send email
def send_email(to_email, subject, body, verification_link=None):
    try:
        print(f"Attempting to send email to {to_email}...")
        print(f"Mail server: {app.config['MAIL_SERVER']}")
        print(f"Mail port: {app.config['MAIL_PORT']}")
        print(f"Mail username: {app.config['MAIL_USERNAME']}")
        if verification_link:
            print(f"\n=== VERIFICATION LINK (for testing): {verification_link} ===")
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Email error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        if verification_link:
            print(f"\n=== VERIFICATION LINK (fallback): {verification_link} ===")
        return False

# Helper function to validate password strength
def is_strong_password(password):
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()" for c in password):
        return False
    return True

with app.app_context():
    db.create_all()
    # Create default admin user if not exists
    admin_email = "admin@attendance.com"
    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        # Default password: Admin@123
        default_admin = User(
            email=admin_email,
            name="Admin User",
            password=generate_password_hash("Admin@123"),
            verified=True,
            role="admin",
            first_login=True
        )
        db.session.add(default_admin)
        db.session.commit()
        print(f"\n=== Default admin account created! ===")
        print(f"Email: {admin_email}")
        print(f"Password: Admin@123")
        print("Please change this password on first login!\n")

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Invalid email or password', 'error')
        elif not user.verified:
            flash('Please verify your email before logging in', 'error')
        elif user.password and check_password_hash(user.password, password):
            login_user(user)
            if user.first_login:
                flash('Please change your password for security.', 'warning')
                return redirect(url_for('change_password'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        elif not is_strong_password(password):
            flash('Password must be at least 8 characters long, include uppercase, lowercase, number, and special character!', 'error')
        else:
            # Generate verification token
            verification_token = generate_verification_token()
            verification_token_expiry = datetime.utcnow() + timedelta(hours=24)
            
            user = User(
                email=email,
                name=name,
                password=generate_password_hash(password),
                first_login=False,
                verified=False,
                verification_token=verification_token,
                verification_token_expiry=verification_token_expiry
            )
            db.session.add(user)
            db.session.commit()
            
            # Send verification email
            verification_link = url_for('verify_email', token=verification_token, _external=True)
            subject = 'Verify Your Email - Attendance System'
            body = f'''Hello {name},

Thank you for registering! Please click the link below to verify your email address:

{verification_link}

This link will expire in 24 hours.

Best regards,
Attendance System Team'''
            email_sent = send_email(email, subject, body, verification_link=verification_link)
            
            if email_sent:
                flash('Account created successfully! Please check your email to verify your account.', 'success')
            else:
                # Show verification link directly in flash message if email fails
                flash(f'Account created! Email verification failed, but you can verify using this link: {verification_link}', 'warning')
                
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Invalid verification link', 'error')
        return redirect(url_for('login'))
    if user.verified:
        flash('Email already verified', 'info')
        return redirect(url_for('login'))
    if datetime.utcnow() > user.verification_token_expiry:
        flash('Verification link has expired. Please register again.', 'error')
        return redirect(url_for('login'))
    
    user.verified = True
    user.verification_token = None
    user.verification_token_expiry = None
    db.session.commit()
    flash('Email verified successfully! Please login.', 'success')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        if current_user.google_id and not current_user.password:
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            if new_password != confirm_password:
                flash('Passwords do not match', 'error')
            elif not is_strong_password(new_password):
                flash('Password must be at least 8 characters long, include uppercase, lowercase, number, and special character!', 'error')
            else:
                current_user.password = generate_password_hash(new_password)
                current_user.first_login = False
                db.session.commit()
                flash('Password set successfully!', 'success')
                return redirect(url_for('dashboard'))
        else:
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('Passwords do not match', 'error')
            elif not is_strong_password(new_password):
                flash('Password must be at least 8 characters long, include uppercase, lowercase, number, and special character!', 'error')
            else:
                current_user.password = generate_password_hash(new_password)
                current_user.first_login = False
                db.session.commit()
                flash('Password changed successfully!', 'success')
                return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    temp_password = None
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            temp_password = generate_password()
            user.password = generate_password_hash(temp_password)
            db.session.commit()
            subject = 'Password Reset - Attendance System'
            body = f'''Hello,

Your password has been reset. Here's your new temporary password:
{temp_password}

Please login and change your password immediately.

Best regards,
Attendance System Team'''
            email_sent = send_email(email, subject, body)
            if email_sent:
                flash('A temporary password has been sent to your email.', 'success')
                temp_password = None  # Don't show on screen if email sent
            else:
                flash('Password reset successful! Your temporary password is shown below.', 'warning')
        else:
            flash('If the email exists, we have sent a reset message.', 'info')
    return render_template('forgot_password.html', temp_password=temp_password)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # Clear all session data
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    
    # Basic Stats
    total_students = Student.query.filter_by(user_id=current_user.id).count()
    today_attendance = Attendance.query.filter_by(user_id=current_user.id, date=today).all()
    present_today = sum(1 for a in today_attendance if a.status == 'Present')
    absent_today = sum(1 for a in today_attendance if a.status == 'Absent')
    
    # Attendance Percentage
    all_attendance = Attendance.query.filter_by(user_id=current_user.id).all()
    total_attendance_records = len(all_attendance)
    total_present = sum(1 for a in all_attendance if a.status == 'Present')
    attendance_percentage = round((total_present / total_attendance_records * 100), 1) if total_attendance_records > 0 else 0
    
    # Defaulters (attendance < 75%)
    defaulters_count = 0
    for student in Student.query.filter_by(user_id=current_user.id).all():
        student_attendance = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id).all()
        if len(student_attendance) > 0:
            student_present = sum(1 for a in student_attendance if a.status == 'Present')
            student_percent = (student_present / len(student_attendance)) * 100
            if student_percent < 75:
                defaulters_count += 1
    
    # Year-wise student distribution
    fy_students = Student.query.filter_by(user_id=current_user.id, year='FY').count()
    sy_students = Student.query.filter_by(user_id=current_user.id, year='SY').count()
    ty_students = Student.query.filter_by(user_id=current_user.id, year='TY').count()
    
    # Class-wise attendance percentage (simple)
    class_names = list(set([s.class_name for s in Student.query.filter_by(user_id=current_user.id).all()])) if Student.query.filter_by(user_id=current_user.id).count() > 0 else []
    class_attendance = []
    for cls in class_names:
        class_students = Student.query.filter_by(user_id=current_user.id, class_name=cls).all()
        class_student_ids = [s.id for s in class_students]
        class_attendance_records = Attendance.query.filter(Attendance.user_id == current_user.id, Attendance.student_id.in_(class_student_ids)).all()
        if class_attendance_records:
            class_present = sum(1 for a in class_attendance_records if a.status == 'Present')
            class_percent = round((class_present / len(class_attendance_records)) * 100, 1)
            class_attendance.append({"name": cls, "percent": class_percent})
    
    # This month's attendance summary
    now = datetime.utcnow()
    first_day_of_month = datetime(now.year, now.month, 1).date()
    last_day_of_month = datetime(now.year, now.month + 1, 1).date() if now.month < 12 else datetime(now.year + 1, 1, 1).date()
    month_attendance = Attendance.query.filter(Attendance.user_id == current_user.id, Attendance.date >= first_day_of_month, Attendance.date < last_day_of_month).all()
    month_present = sum(1 for a in month_attendance if a.status == 'Present')
    month_absent = sum(1 for a in month_attendance if a.status == 'Absent')
    
    # Recent Activity (mock for now - we'll use recent attendance and students)
    recent_activity = []
    # Add recently marked attendance (last 5)
    recent_attendance = Attendance.query.filter_by(user_id=current_user.id).order_by(Attendance.date.desc()).limit(5).all()
    for rec in recent_attendance:
        student = Student.query.filter_by(user_id=current_user.id, id=rec.student_id).first()
        if student:
            recent_activity.append({
                "type": "attendance",
                "icon": "fa-clipboard-check",
                "message": f"{student.name} marked {rec.status} on {rec.date}",
                "time": rec.date
            })
    # Add newly added students (last 3)
    recent_students = Student.query.filter_by(user_id=current_user.id).order_by(Student.id.desc()).limit(3).all()
    for student in recent_students:
        recent_activity.append({
            "type": "student",
            "icon": "fa-user-plus",
            "message": f"New student added: {student.name} ({student.roll_no})",
            "time": today  # Mock since we don't have created_at
        })
    # Sort recent activity by date (descending)
    recent_activity.sort(key=lambda x: x["time"], reverse=True)
    recent_activity = recent_activity[:8]  # Take top 8
    
    return render_template('dashboard.html',
                         total_students=total_students,
                         present_today=present_today,
                         absent_today=absent_today,
                         attendance_percentage=attendance_percentage,
                         defaulters_count=defaulters_count,
                         fy_students=fy_students,
                         sy_students=sy_students,
                         ty_students=ty_students,
                         class_attendance=class_attendance,
                         month_present=month_present,
                         month_absent=month_absent,
                         recent_activity=recent_activity,
                         today=today)

@app.route('/students')
@login_required
def students():
    search_query = request.args.get('search', '')
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class_filter', '')
    
    query = Student.query.filter_by(user_id=current_user.id)
    
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            (Student.name.ilike(search)) |
            (Student.roll_no.ilike(search)) |
            (Student.email.ilike(search)) |
            (Student.class_name.ilike(search))
        )
    
    if selected_year:
        query = query.filter_by(year=selected_year)
    
    if selected_class:
        query = query.filter_by(class_name=selected_class)
    
    students = query.all()
    
    # Get unique years and classes for filters
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    years = ['FY', 'SY', 'TY']
    classes = list(set([s.class_name for s in all_students])) if all_students else []
    
    return render_template('students.html', 
                         students=students, 
                         search_query=search_query,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         years=years,
                         classes=classes)

@app.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        class_name = request.form['class_name']
        year = request.form['year']
        email = request.form['email'].strip().lower() if request.form['email'] else None
        
        existing_student = Student.query.filter_by(user_id=current_user.id, roll_no=roll_no).first()
        if existing_student:
            flash('Student with this roll number already exists', 'error')
        elif email and Student.query.filter_by(user_id=current_user.id, email=email).first():
            flash('Student with this email already exists', 'error')
        else:
            student = Student(user_id=current_user.id, roll_no=roll_no, name=name, class_name=class_name, year=year, email=email)
            db.session.add(student)
            db.session.commit()
            flash('Student added successfully', 'success')
            return redirect(url_for('students'))
    return render_template('add_student.html', years=['FY', 'SY', 'TY'])

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.filter_by(user_id=current_user.id, id=student_id).first_or_404()
    if request.method == 'POST':
        student.roll_no = request.form['roll_no']
        student.name = request.form['name']
        student.class_name = request.form['class_name']
        student.year = request.form['year']
        student.email = request.form['email'].strip().lower() if request.form['email'] else None
        db.session.commit()
        flash('Student updated successfully', 'success')
        return redirect(url_for('students'))
    return render_template('edit_student.html', student=student, years=['FY', 'SY', 'TY'])

@app.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.filter_by(user_id=current_user.id, id=student_id).first_or_404()
    Attendance.query.filter_by(user_id=current_user.id, student_id=student_id).delete()
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully', 'success')
    return redirect(url_for('students'))

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if request.method == 'POST':
        selected_year = request.form.get('year', '')
        selected_class = request.form.get('class_name', '')
    else:
        selected_year = request.args.get('year', '')
        selected_class = request.args.get('class_name', '')
    
    # Get all unique classes for filter
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in all_students])) if all_students else []
    years = ['FY', 'SY', 'TY']
    
    if request.method == 'POST':
        date = request.form['date']
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        # Get filtered students for saving attendance
        query = Student.query.filter_by(user_id=current_user.id)
        if selected_year:
            query = query.filter_by(year=selected_year)
        if selected_class:
            query = query.filter_by(class_name=selected_class)
        students = query.all()
        
        for student in students:
            status = request.form.get(f'status_{student.id}', 'Absent')
            existing = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id, date=date_obj).first()
            if existing:
                existing.status = status
            else:
                attendance = Attendance(user_id=current_user.id, student_id=student.id, date=date_obj, status=status)
                db.session.add(attendance)
            
            # Sync to Google Cloud and Sheets if available
            if google_services:
                google_services.sync_attendance_to_cloud(
                    student.name,
                    student.roll_no,
                    student.year,
                    date,
                    status
                )
        db.session.commit()
        flash('Attendance marked and synced successfully', 'success')
        # Redirect back with filters
        return redirect(url_for('attendance', year=selected_year, class_name=selected_class))
    
    today = datetime.utcnow().date()
    
    # Get filtered students for display
    query = Student.query.filter_by(user_id=current_user.id)
    if selected_year:
        query = query.filter_by(year=selected_year)
    if selected_class:
        query = query.filter_by(class_name=selected_class)
    students = query.all()
    
    attendance_data = {}
    for student in students:
        existing = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id, date=today).first()
        attendance_data[student.id] = existing.status if existing else 'Present'
    
    return render_template('attendance.html', 
                         students=students, 
                         today=today, 
                         attendance_data=attendance_data,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         years=years,
                         class_names=class_names)

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in students])) if students else []
    years = ['FY', 'SY', 'TY']
    
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    if selected_year:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, year=selected_year).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if selected_class:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, class_name=selected_class).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if status:
        query = query.filter(Attendance.status == status)
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    report_data = []
    for record in attendance_records:
        student = Student.query.filter_by(user_id=current_user.id, id=record.student_id).first()
        if student:
            report_data.append({
                'date': record.date,
                'roll_no': student.roll_no,
                'name': student.name,
                'class': student.class_name,
                'status': record.status
            })
    
    return render_template('report.html', 
                         report_data=report_data, 
                         class_names=class_names,
                         years=years,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         start_date=start_date,
                         end_date=end_date,
                         status=status)

@app.route('/download_report_excel')
@login_required
def download_report_excel():
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    if selected_year:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, year=selected_year).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if selected_class:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, class_name=selected_class).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if status:
        query = query.filter(Attendance.status == status)
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    data = []
    for record in attendance_records:
        student = Student.query.filter_by(user_id=current_user.id, id=record.student_id).first()
        if student:
            data.append({
                'Date': record.date,
                'Roll No': student.roll_no,
                'Name': student.name,
                'Class': student.class_name,
                'Status': record.status
            })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance Report')
    output.seek(0)
    
    return send_file(output, 
                     download_name=f'attendance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/download_report_pdf')
@login_required
def download_report_pdf():
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    if selected_year:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, year=selected_year).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if selected_class:
        student_ids = [s.id for s in Student.query.filter_by(user_id=current_user.id, class_name=selected_class).all()]
        query = query.filter(Attendance.student_id.in_(student_ids))
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if status:
        query = query.filter(Attendance.status == status)
    
    attendance_records = query.order_by(Attendance.date.desc()).all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title = Paragraph("Attendance Report", styles['Title'])
    elements.append(title)
    elements.append(Paragraph("<br/>", styles['Normal']))
    
    table_data = [['Date', 'Roll No', 'Name', 'Class', 'Status']]
    for record in attendance_records:
        student = Student.query.filter_by(user_id=current_user.id, id=record.student_id).first()
        if student:
            table_data.append([
                str(record.date),
                student.roll_no,
                student.name,
                student.class_name,
                record.status
            ])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(buffer,
                     download_name=f'attendance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
                     as_attachment=True,
                     mimetype='application/pdf')

@app.route('/defaulters')
@login_required
def defaulters():
    threshold = 75
    years = ['FY', 'SY', 'TY']
    
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    
    # Get all unique classes for filter
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in all_students])) if all_students else []
    
    query = Student.query.filter_by(user_id=current_user.id)
    if selected_year:
        query = query.filter_by(year=selected_year)
    if selected_class:
        query = query.filter_by(class_name=selected_class)
    students = query.all()
    
    defaulters_list = []
    
    for student in students:
        total_days = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id).count()
        if total_days == 0:
            percentage = 0
        else:
            present_days = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id, status='Present').count()
            percentage = (present_days / total_days) * 100
        
        if percentage < threshold:
            defaulters_list.append({
                'roll_no': student.roll_no,
                'name': student.name,
                'class': student.class_name,
                'total_days': total_days,
                'present_days': present_days if total_days > 0 else 0,
                'percentage': round(percentage, 2)
            })
    
    return render_template('defaulters.html', 
                         defaulters=defaulters_list, 
                         threshold=threshold,
                         years=years,
                         class_names=class_names,
                         selected_year=selected_year,
                         selected_class=selected_class)

if __name__ == '__main__':
    app.run(debug=True)

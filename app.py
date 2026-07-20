from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta, UTC
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
from database.models import User, Student, Attendance, Subject, Category

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

# Icon emoji mapping (FA class → emoji)
ICON_EMOJIS = {
    "fa-book": "📚",
    "fa-calculator": "🧮",
    "fa-code": "💻",
    "fa-microchip": "🔌",
    "fa-flask": "🧪",
    "fa-paint-brush": "🎨",
    "fa-music": "🎵",
    "fa-globe": "🌍",
    "fa-chart-line": "📈",
    "fa-language": "🗣️",
    "fa-database": "🗄️",
    "fa-server": "🖥️",
    "fa-puzzle-piece": "🧩",
    "fa-futbol": "⚽",
    "fa-heartbeat": "💓",
    "fa-infinity": "♾️",
}

# Add Jinja global
@app.context_processor
def utility_processor():
    return dict(icon_to_emoji=lambda fa_class: ICON_EMOJIS.get(fa_class, "📚"))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    today = datetime.now(UTC).date()
    
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
    
    # Year-wise student distribution (using current_year property)
    all_students_list = Student.query.filter_by(user_id=current_user.id).all()
    fy_students = sum(1 for s in all_students_list if s.current_year == 'FY')
    sy_students = sum(1 for s in all_students_list if s.current_year == 'SY')
    ty_students = sum(1 for s in all_students_list if s.current_year == 'TY')
    
    # Class-wise attendance percentage (simple)
    class_names = list(set([s.class_name for s in all_students_list])) if all_students_list else []
    class_attendance = []
    for cls in class_names:
        class_students = [s for s in all_students_list if s.class_name == cls]
        class_student_ids = [s.id for s in class_students]
        class_attendance_records = Attendance.query.filter(Attendance.user_id == current_user.id, Attendance.student_id.in_(class_student_ids)).all()
        if class_attendance_records:
            class_present = sum(1 for a in class_attendance_records if a.status == 'Present')
            class_percent = round((class_present / len(class_attendance_records)) * 100, 1)
            class_attendance.append({"name": cls, "percent": class_percent})
    
    # This month's attendance summary
    now = datetime.now(UTC)
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
    from datetime import datetime
    today_year = datetime.today().year
    
    search_query = request.args.get('search', '')
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class_filter', '')
    selected_admission_year = request.args.get('admission_year', '')
    
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    
    # Filter students
    filtered_students = all_students
    if search_query:
        search = search_query.lower()
        filtered_students = [
            s for s in filtered_students 
            if search in s.name.lower() 
            or search in s.roll_no.lower()
            or (s.email and search in s.email.lower())
            or search in s.class_name.lower()
        ]
    
    if selected_year:
        filtered_students = [s for s in filtered_students if s.current_year == selected_year]
    
    if selected_class:
        filtered_students = [s for s in filtered_students if s.class_name == selected_class]
    
    if selected_admission_year:
        filtered_students = [s for s in filtered_students if s.admission_year == int(selected_admission_year)]
    
    # Get unique values for filters
    years = ['FY', 'SY', 'TY']
    classes = list(set([s.class_name for s in all_students])) if all_students else []
    admission_years = sorted(list(set([s.admission_year for s in all_students])), reverse=True) if all_students else []
    
    return render_template('students.html', 
                         students=filtered_students, 
                         search_query=search_query,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         selected_admission_year=selected_admission_year,
                         years=years,
                         classes=classes,
                         admission_years=admission_years,
                         today_year=today_year)

@app.route('/upload_students', methods=['POST'])
@login_required
def upload_students():
    import os
    from werkzeug.utils import secure_filename
    from excel.import_excel import import_students_from_file
    
    # Get file from request
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('students'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('students'))
    
    # Get admission year from form
    admission_year = None
    if 'admission_year' in request.form and request.form['admission_year']:
        admission_year = int(request.form['admission_year'])
    
    # Validate file extension
    allowed_extensions = {'csv', 'xlsx', 'xls'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        flash('Invalid file type. Please use CSV or Excel files only.', 'error')
        return redirect(url_for('students'))
    
    # Save file temporarily
    temp_dir = 'temp_uploads'
    os.makedirs(temp_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    temp_path = os.path.join(temp_dir, filename)
    file.save(temp_path)
    
    try:
        # Import students
        imported_count, duplicates, errors = import_students_from_file(temp_path, current_user.id, admission_year)
        
        # Show success message
        if imported_count > 0:
            flash(f'{imported_count} students imported successfully!', 'success')
        
        if duplicates:
            duplicate_names = [f"{d['name']} ({d['roll_no']})" for d in duplicates]
            flash(f'Skipped {len(duplicates)} duplicate(s): {", ".join(duplicate_names)}', 'warning')
        
        if errors:
            for error in errors:
                flash(error, 'error')
                
    except Exception as e:
        flash(f'Error importing students: {str(e)}', 'error')
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            print(f'Error removing temp file: {e}')
    
    return redirect(url_for('students'))


@app.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        admission_year = int(request.form['admission_year'])
        email = request.form['email'].strip().lower() if request.form['email'] else None
        
        existing_student = Student.query.filter_by(user_id=current_user.id, roll_no=roll_no).first()
        if existing_student:
            flash('Student with this roll number already exists', 'error')
        elif email and Student.query.filter_by(user_id=current_user.id, email=email).first():
            flash('Student with this email already exists', 'error')
        else:
            student = Student(
                user_id=current_user.id,
                roll_no=roll_no,
                name=name,
                admission_year=admission_year,
                email=email
            )
            db.session.add(student)
            db.session.commit()
            flash('Student added successfully', 'success')
            return redirect(url_for('students'))
    # Generate list of possible admission years (last 10 years + next 1)
    from datetime import datetime
    current_year = datetime.today().year
    admission_years = [str(y) for y in range(current_year - 10, current_year + 2)]
    return render_template('add_student.html', admission_years=admission_years)

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.filter_by(user_id=current_user.id, id=student_id).first_or_404()
    if request.method == 'POST':
        student.roll_no = request.form['roll_no']
        student.name = request.form['name']
        student.admission_year = int(request.form['admission_year'])
        student.email = request.form['email'].strip().lower() if request.form['email'] else None
        db.session.commit()
        flash('Student updated successfully', 'success')
        return redirect(url_for('students'))
    # Generate list of possible admission years
    from datetime import datetime
    current_year = datetime.today().year
    admission_years = [str(y) for y in range(current_year - 10, current_year + 2)]
    return render_template('edit_student.html', student=student, admission_years=admission_years)

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
    # Get filters, checking session for remembered subject first
    if request.method == 'POST':
        selected_year = request.form.get('year', '')
        selected_class = request.form.get('class_name', '')
        selected_subject = request.form.get('subject', '')
        selected_admission_year = request.form.get('admission_year', '')
        # Remember subject in session
        if selected_subject:
            session['selected_subject'] = selected_subject
        elif 'selected_subject' in session:
            selected_subject = session['selected_subject']
    else:
        selected_year = request.args.get('year', '')
        selected_class = request.args.get('class_name', '')
        selected_subject = request.args.get('subject', session.get('selected_subject', ''))
        selected_admission_year = request.args.get('admission_year', '')
        # Remember subject in session
        if selected_subject:
            session['selected_subject'] = selected_subject
    
    # Get all students and generate filters
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in all_students])) if all_students else []
    years = ['FY', 'SY', 'TY']
    admission_years = sorted(list(set([s.admission_year for s in all_students])), reverse=True) if all_students else []
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        date = request.form['date']
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        subject_id = int(selected_subject) if selected_subject else None
        
        # Filter students
        students = all_students
        if selected_year:
            students = [s for s in students if s.current_year == selected_year]
        if selected_class:
            students = [s for s in students if s.class_name == selected_class]
        if selected_admission_year:
            students = [s for s in students if s.admission_year == int(selected_admission_year)]
        
        for student in students:
            status = request.form.get(f'status_{student.id}', 'Absent')
            existing = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id, date=date_obj, subject_id=subject_id).first()
            if existing:
                existing.status = status
            else:
                attendance = Attendance(user_id=current_user.id, student_id=student.id, subject_id=subject_id, date=date_obj, status=status)
                db.session.add(attendance)
            
            # Sync to Google Cloud and Sheets if available
            if google_services:
                google_services.sync_attendance_to_cloud(
                    student.name,
                    student.roll_no,
                    student.current_year,
                    date,
                    status
                )
        db.session.commit()
        flash('Attendance marked and synced successfully', 'success')
        # Redirect back with filters
        return redirect(url_for('attendance', 
                               year=selected_year, 
                               class_name=selected_class, 
                               subject=selected_subject,
                               admission_year=selected_admission_year))
    
    today = datetime.now(UTC).date()
    subject_id = int(selected_subject) if selected_subject else None
    
    # Filter students for display
    students = all_students
    if selected_year:
        students = [s for s in students if s.current_year == selected_year]
    if selected_class:
        students = [s for s in students if s.class_name == selected_class]
    if selected_admission_year:
        students = [s for s in students if s.admission_year == int(selected_admission_year)]
    
    attendance_data = {}
    for student in students:
        existing = Attendance.query.filter_by(user_id=current_user.id, student_id=student.id, date=today, subject_id=subject_id).first()
        attendance_data[student.id] = existing.status if existing else 'Present'
    
    return render_template('attendance.html', 
                         students=students, 
                         today=today, 
                         attendance_data=attendance_data,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         selected_subject=selected_subject,
                         selected_admission_year=selected_admission_year,
                         years=years,
                         class_names=class_names,
                         admission_years=admission_years,
                         subjects=subjects)

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in all_students])) if all_students else []
    years = ['FY', 'SY', 'TY']
    admission_years = sorted(list(set([s.admission_year for s in all_students])), reverse=True) if all_students else []
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    selected_admission_year = request.args.get('admission_year', '')
    selected_subject = request.args.get('subject', session.get('selected_subject', ''))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    # Remember subject in session
    if selected_subject:
        session['selected_subject'] = selected_subject
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    
    # Get filtered student IDs
    filtered_student_ids = [s.id for s in all_students]
    if selected_year:
        filtered_student_ids = [s.id for s in all_students if s.current_year == selected_year]
    if selected_class:
        filtered_student_ids = [s.id for s in all_students if s.class_name == selected_class and s.id in filtered_student_ids]
    if selected_admission_year:
        filtered_student_ids = [s.id for s in all_students if s.admission_year == int(selected_admission_year) and s.id in filtered_student_ids]
    
    query = query.filter(Attendance.student_id.in_(filtered_student_ids))
    
    # Apply subject filter
    if selected_subject:
        query = query.filter(Attendance.subject_id == int(selected_subject))
    
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
        subject = Subject.query.filter_by(id=record.subject_id).first() if record.subject_id else None
        if student:
            report_data.append({
                'date': record.date,
                'roll_no': student.roll_no,
                'name': student.name,
                'class': student.class_name,
                'subject': subject.name if subject else '',
                'status': record.status
            })
    
    return render_template('report.html', 
                         report_data=report_data, 
                         class_names=class_names,
                         years=years,
                         admission_years=admission_years,
                         subjects=subjects,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         selected_admission_year=selected_admission_year,
                         selected_subject=selected_subject,
                         start_date=start_date,
                         end_date=end_date,
                         status=status)

@app.route('/download_report_excel')
@login_required
def download_report_excel():
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    selected_admission_year = request.args.get('admission_year', '')
    selected_subject = request.args.get('subject', session.get('selected_subject', ''))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    
    # Get filtered student IDs
    filtered_student_ids = [s.id for s in all_students]
    if selected_year:
        filtered_student_ids = [s.id for s in all_students if s.current_year == selected_year]
    if selected_class:
        filtered_student_ids = [s.id for s in all_students if s.class_name == selected_class and s.id in filtered_student_ids]
    if selected_admission_year:
        filtered_student_ids = [s.id for s in all_students if s.admission_year == int(selected_admission_year) and s.id in filtered_student_ids]
    
    query = query.filter(Attendance.student_id.in_(filtered_student_ids))
    
    # Apply subject filter
    if selected_subject:
        query = query.filter(Attendance.subject_id == int(selected_subject))
    
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
        subject = Subject.query.filter_by(id=record.subject_id).first() if record.subject_id else None
        if student:
            data.append({
                'Date': record.date,
                'Roll No': student.roll_no,
                'Name': student.name,
                'Class': student.class_name,
                'Subject': subject.name if subject else '',
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
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    selected_year = request.args.get('year', '')
    selected_class = request.args.get('class', '')
    selected_admission_year = request.args.get('admission_year', '')
    selected_subject = request.args.get('subject', session.get('selected_subject', ''))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')
    
    query = Attendance.query.filter_by(user_id=current_user.id)
    
    # Get filtered student IDs
    filtered_student_ids = [s.id for s in all_students]
    if selected_year:
        filtered_student_ids = [s.id for s in all_students if s.current_year == selected_year]
    if selected_class:
        filtered_student_ids = [s.id for s in all_students if s.class_name == selected_class and s.id in filtered_student_ids]
    if selected_admission_year:
        filtered_student_ids = [s.id for s in all_students if s.admission_year == int(selected_admission_year) and s.id in filtered_student_ids]
    
    query = query.filter(Attendance.student_id.in_(filtered_student_ids))
    
    # Apply subject filter
    if selected_subject:
        query = query.filter(Attendance.subject_id == int(selected_subject))
    
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
    
    table_data = [['Date', 'Roll No', 'Name', 'Class', 'Subject', 'Status']]
    for record in attendance_records:
        student = Student.query.filter_by(user_id=current_user.id, id=record.student_id).first()
        subject = Subject.query.filter_by(id=record.subject_id).first() if record.subject_id else None
        if student:
            table_data.append([
                str(record.date),
                student.roll_no,
                student.name,
                student.class_name,
                subject.name if subject else '',
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
    selected_admission_year = request.args.get('admission_year', '')
    
    # Get all unique classes for filter
    all_students = Student.query.filter_by(user_id=current_user.id).all()
    class_names = list(set([s.class_name for s in all_students])) if all_students else []
    admission_years = sorted(list(set([s.admission_year for s in all_students])), reverse=True) if all_students else []
    
    # Filter students
    students = all_students
    if selected_year:
        students = [s for s in students if s.current_year == selected_year]
    if selected_class:
        students = [s for s in students if s.class_name == selected_class]
    if selected_admission_year:
        students = [s for s in students if s.admission_year == int(selected_admission_year)]
    
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
                         admission_years=admission_years,
                         selected_year=selected_year,
                         selected_class=selected_class,
                         selected_admission_year=selected_admission_year)

@app.route('/categories')
@login_required
def categories():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('categories.html', categories=categories)

@app.route('/add_category', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        code = request.form['code']
        name = request.form.get('name', '')
        existing = Category.query.filter_by(user_id=current_user.id, code=code).first()
        if existing:
            flash('Category with this code already exists', 'error')
        else:
            category = Category(user_id=current_user.id, code=code, name=name)
            db.session.add(category)
            db.session.commit()
            flash('Category added successfully', 'success')
            return redirect(url_for('categories'))
    return render_template('add_category.html')

@app.route('/edit_category/<int:category_id>', methods=['GET', 'POST'])
@login_required
def edit_category(category_id):
    category = Category.query.filter_by(user_id=current_user.id, id=category_id).first_or_404()
    if request.method == 'POST':
        category.code = request.form['code']
        category.name = request.form.get('name', '')
        db.session.commit()
        flash('Category updated successfully', 'success')
        return redirect(url_for('categories'))
    return render_template('edit_category.html', category=category)

@app.route('/delete_category/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = Category.query.filter_by(user_id=current_user.id, id=category_id).first_or_404()
    Subject.query.filter_by(category_id=category_id).update({'category_id': None})
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully', 'success')
    return redirect(url_for('categories'))

@app.route('/subjects')
@login_required
def subjects():
    search_query = request.args.get('search', '')
    selected_category = request.args.get('category', '')
    query = Subject.query.filter_by(user_id=current_user.id)
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(Subject.name.ilike(search))
    if selected_category:
        query = query.filter_by(category_id=selected_category)
    subjects = query.all()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('subjects.html', subjects=subjects, categories=categories, search_query=search_query, selected_category=selected_category)

@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        name = request.form['name']
        icon = request.form.get('icon', '📚')
        category_id = request.form.get('category_id')
        category_id = int(category_id) if category_id else None
        subject = Subject(user_id=current_user.id, name=name, icon=icon, category_id=category_id)
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully', 'success')
        return redirect(url_for('subjects'))
    return render_template('add_subject.html', categories=categories)

@app.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    subject = Subject.query.filter_by(user_id=current_user.id, id=subject_id).first_or_404()
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        subject.name = request.form['name']
        subject.icon = request.form.get('icon', '📚')
        category_id = request.form.get('category_id')
        subject.category_id = int(category_id) if category_id else None
        db.session.commit()
        flash('Subject updated successfully', 'success')
        return redirect(url_for('subjects'))
    return render_template('edit_subject.html', subject=subject, categories=categories)

@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.filter_by(user_id=current_user.id, id=subject_id).first_or_404()
    Attendance.query.filter_by(subject_id=subject_id).update({'subject_id': None})
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully', 'success')
    return redirect(url_for('subjects'))

if __name__ == '__main__':
    app.run(debug=True)

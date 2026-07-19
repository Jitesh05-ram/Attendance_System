from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from database.models import Student, Attendance
from datetime import datetime

def generate_attendance_report(date_str, file_path):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    records = Attendance.query.filter_by(date=date_obj).all()
    
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    
    c.drawString(100, height - 100, f"Attendance Report - {date_str}")
    
    y = height - 150
    for record in records:
        student = Student.query.get(record.student_id)
        c.drawString(100, y, f"Roll No: {student.roll_no}, Name: {student.name}, Status: {record.status}")
        y -= 20
    
    c.save()

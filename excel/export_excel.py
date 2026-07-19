import pandas as pd
from database.models import Student, Attendance
from datetime import datetime

def export_attendance_to_excel(date_str, file_path):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    records = Attendance.query.filter_by(date=date_obj).all()
    data = []
    for record in records:
        student = Student.query.get(record.student_id)
        data.append({
            'Roll No': student.roll_no,
            'Name': student.name,
            'Class': student.class_name,
            'Status': record.status
        })
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)

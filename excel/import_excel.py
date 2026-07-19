import pandas as pd
from database.models import Student
from database.db import db

def import_students_from_excel(file_path):
    df = pd.read_excel(file_path)
    for index, row in df.iterrows():
        roll_no = str(row['Roll No'])
        name = row['Name']
        class_name = row['Class']
        existing = Student.query.filter_by(roll_no=roll_no).first()
        if not existing:
            student = Student(roll_no=roll_no, name=name, class_name=class_name)
            db.session.add(student)
    db.session.commit()

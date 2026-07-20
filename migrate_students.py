from app import app
from database.db import db
from database.models import Student
from datetime import datetime

def migrate_students():
    with app.app_context():
        print("Starting student migration...")
        
        # Get current academic year to estimate admission year
        today = datetime.today()
        if today.month >= 7:
            current_academic_year = today.year
        else:
            current_academic_year = today.year - 1
        
        # Get all students (we need to check if they have old fields)
        # First, check if 'year' and 'class_name' columns exist (for safety)
        try:
            # Try to query with old fields
            students = Student.query.all()
            # If we get here, we need to migrate
            for student in students:
                # Estimate admission year based on old 'year' field
                # But wait, in SQLAlchemy, if we removed the columns, we can't access them
                # So let's use raw SQL to get old data!
                pass
        except Exception as e:
            print("Using raw SQL for migration...")
        
        # Use raw SQL to check and migrate
        from sqlalchemy import text
        conn = db.engine.connect()
        
        # First, check if year and class_name columns exist (SQLite specific)
        result = conn.execute(text("PRAGMA table_info(student)"))
        columns = [row[1] for row in result]
        
        if 'year' in columns and 'class_name' in columns:
            print("Old columns found, migrating...")
            # Get all old data
            old_students = conn.execute(text("SELECT id, year, class_name FROM student"))
            
            for row in old_students:
                student_id, old_year, old_class_name = row
                
                # Estimate admission year
                # If class name starts with two digits (like 26FYBSC), use that
                admission_year = None
                if old_class_name and len(old_class_name) >= 2 and old_class_name[:2].isdigit():
                    admission_year = 2000 + int(old_class_name[:2])
                else:
                    # Fallback: calculate based on old year
                    if old_year == 'FY':
                        admission_year = current_academic_year
                    elif old_year == 'SY':
                        admission_year = current_academic_year - 1
                    elif old_year == 'TY':
                        admission_year = current_academic_year - 2
                    else:
                        admission_year = current_academic_year
                
                # Update the student
                conn.execute(
                    text("UPDATE student SET admission_year = :admission_year WHERE id = :id"),
                    {"admission_year": admission_year, "id": student_id}
                )
                print(f"Updated student {student_id}: old year={old_year}, class={old_class_name} → admission_year={admission_year}")
            
            # Now, drop the old columns (SQLite way - need to recreate table)
            print("Recreating student table without old columns...")
            # Get all existing data
            all_students = conn.execute(text("SELECT id, user_id, roll_no, name, admission_year, email FROM student"))
            students_data = [dict(row) for row in all_students]
            
            # Drop old table
            conn.execute(text("DROP TABLE student"))
            db.session.commit()
            
            # Create new table (SQLAlchemy will handle this when app starts, but let's do it now)
            db.create_all()
            
            # Reinsert data
            for s in students_data:
                conn.execute(
                    text("INSERT INTO student (id, user_id, roll_no, name, admission_year, email) VALUES (:id, :user_id, :roll_no, :name, :admission_year, :email)"),
                    s
                )
            db.session.commit()
            print("Migration complete!")
        else:
            print("No migration needed, old columns not found.")
        
        conn.close()

if __name__ == "__main__":
    migrate_students()
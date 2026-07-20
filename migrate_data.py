import sqlite3
from datetime import datetime

def migrate_data():
    print("Starting data migration...")
    
    # Step 1: Connect to backup and new databases
    backup_conn = sqlite3.connect('instance/database_backup.db')
    backup_cursor = backup_conn.cursor()
    
    new_conn = sqlite3.connect('instance/database.db')
    new_cursor = new_conn.cursor()
    
    # Step 2: Migrate users
    print("Migrating users...")
    backup_cursor.execute("SELECT id, email, name, password, google_id, role, first_login, verified, verification_token, verification_token_expiry, created_at FROM user")
    users_data = backup_cursor.fetchall()
    for user_data in users_data:
        (user_id, email, name, password, google_id, role, first_login, verified, verification_token, verification_token_expiry, created_at) = user_data
        new_cursor.execute("""
            INSERT OR IGNORE INTO user (id, email, name, password, google_id, role, first_login, verified, verification_token, verification_token_expiry, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, user_data)
    new_conn.commit()
    
    # Step 3: Migrate students
    print("Migrating students...")
    backup_cursor.execute("SELECT id, user_id, roll_no, name, class_name, year, email FROM student")
    students_data = backup_cursor.fetchall()
    for student_data in students_data:
        (student_id, user_id, roll_no, name, class_name, old_year, email) = student_data
        
        # Calculate admission year
        admission_year = 2026
        if class_name and len(class_name) >= 2 and class_name[:2].isdigit():
            admission_year = 2000 + int(class_name[:2])
        else:
            today = datetime.today()
            current_academic_year = today.year if today.month >= 7 else today.year - 1
            if old_year == 'FY':
                admission_year = current_academic_year
            elif old_year == 'SY':
                admission_year = current_academic_year - 1
            elif old_year == 'TY':
                admission_year = current_academic_year - 2
        
        new_cursor.execute("""
            INSERT OR IGNORE INTO student (id, user_id, roll_no, name, admission_year, email)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, user_id, roll_no, name, admission_year, email))
    new_conn.commit()
    
    # Step 4: Migrate attendance
    print("Migrating attendance...")
    backup_cursor.execute("SELECT id, user_id, student_id, date, status FROM attendance")
    attendance_data = backup_cursor.fetchall()
    for att_data in attendance_data:
        (att_id, user_id, student_id, date_str, status) = att_data
        new_cursor.execute("""
            INSERT OR IGNORE INTO attendance (id, user_id, student_id, subject_id, date, status)
            VALUES (?, ?, ?, NULL, ?, ?)
        """, (att_id, user_id, student_id, date_str, status))
    new_conn.commit()
    
    # Step 5: Seed categories and subjects for all users
    print("Seeding categories and subjects...")
    categories_data = [
        ("MJ5", "Major 5"), ("MJ6", "Major 6"), ("MJ7", "Major 7"),
        ("MJP3", "Major Practical 3"), ("Minor", "Minor Subject"), ("OE", "Open Elective"),
        ("VSC", "VSC Subject"), ("AEC", "AEC Subject"), ("FP", "Field Project"),
        ("Co-Curricular", "Co-Curricular Activity")
    ]
    subjects_data = [
        ("Principles of Operating Systems", "MJ5"), ("Theory of Computation", "MJ6"),
        ("Data Structures", "MJ7"), ("Computer Science Practical 3", "MJP3"),
        ("Vector Space", "Minor"), ("PM-3B Vector Spaces", "Minor"),
        ("Philosophy of Dr.B.R.Ambedkar", "OE"), ("Java Programming", "VSC"),
        ("हिंदी भाषा व्यवహారిక ప్రయోగం", "AEC"), ("Field Project", "FP"),
        ("Introduction to Sports Training & Tests and Measurement", "Co-Curricular")
    ]
    
    new_cursor.execute("SELECT id FROM user")
    user_ids = [row[0] for row in new_cursor.fetchall()]
    
    for user_id in user_ids:
        # Insert categories for this user
        category_id_map = {}
        for (code, name) in categories_data:
            new_cursor.execute("""
                INSERT OR IGNORE INTO category (user_id, code, name)
                VALUES (?, ?, ?)
            """, (user_id, code, name))
            new_conn.commit()
            # Get the id of the inserted or existing category
            new_cursor.execute("SELECT id FROM category WHERE user_id = ? AND code = ?", (user_id, code))
            category_id_map[code] = new_cursor.fetchone()[0]
        
        # Insert subjects for this user
        for (subject_name, category_code) in subjects_data:
            category_id = category_id_map.get(category_code)
            new_cursor.execute("""
                INSERT OR IGNORE INTO subject (user_id, name, category_id)
                VALUES (?, ?, ?)
            """, (user_id, subject_name, category_id))
        new_conn.commit()
    
    backup_conn.close()
    new_conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_data()

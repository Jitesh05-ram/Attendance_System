from app import app
from database.db import db
from database.models import Student
from sqlalchemy import text

with app.app_context():
    try:
        # Try to add year and email columns if they don't exist
        with db.engine.connect() as conn:
            # Check if year column exists
            result = conn.execute(text("PRAGMA table_info(student)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'year' not in columns:
                conn.execute(text("ALTER TABLE student ADD COLUMN year VARCHAR(10) NOT NULL DEFAULT 'FY'"))
                print("Added 'year' column to student table")
            
            if 'email' not in columns:
                conn.execute(text("ALTER TABLE student ADD COLUMN email VARCHAR(150)"))
                print("Added 'email' column to student table")
            
            conn.commit()
    except Exception as e:
        print(f"Error updating database: {e}")
        print("If you're getting an error, you might need to delete the old database.db file and let it recreate.")

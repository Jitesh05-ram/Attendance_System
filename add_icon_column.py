from app import app
from database.db import db
from sqlalchemy import text

with app.app_context():
    try:
        # Add icon column to subject table
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE subject ADD COLUMN icon VARCHAR(50) DEFAULT 'fa-book'"))
            conn.commit()
        print("Successfully added 'icon' column to subject table!")
    except Exception as e:
        print(f"Error: {e}")

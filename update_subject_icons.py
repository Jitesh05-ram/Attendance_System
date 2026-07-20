from app import app
from database.db import db
from database.models import Subject

with app.app_context():
    # Get all subjects
    subjects = Subject.query.all()
    
    # Update all to use fa-book as default Font Awesome icon
    for subject in subjects:
        subject.icon = "fa-book"
    
    db.session.commit()
    print(f"Updated {len(subjects)} subjects!")

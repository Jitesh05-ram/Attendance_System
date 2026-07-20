from app import app
from database.db import db
from database.models import User, Category, Subject

def seed_subjects_for_user(user_email):
    with app.app_context():
        # Find the user
        user = User.query.filter_by(email=user_email).first()
        if not user:
            print(f"User with email {user_email} not found!")
            return
        
        print(f"Seeding subjects and categories for user: {user.name} ({user.email})")
        
        # Define categories from the user's image
        categories_data = [
            {"code": "MJ5", "name": "Major 5"},
            {"code": "MJ6", "name": "Major 6"},
            {"code": "MJ7", "name": "Major 7"},
            {"code": "MJP3", "name": "Major Practical 3"},
            {"code": "Minor", "name": "Minor Subject"},
            {"code": "OE", "name": "Open Elective"},
            {"code": "VSC", "name": "VSC Subject"},
            {"code": "AEC", "name": "AEC Subject"},
            {"code": "FP", "name": "Field Project"},
            {"code": "Co-Curricular", "name": "Co-Curricular Activity"}
        ]
        
        # Define subjects with their categories
        subjects_data = [
            {"name": "Principles of Operating Systems", "category_code": "MJ5"},
            {"name": "Theory of Computation", "category_code": "MJ6"},
            {"name": "Data Structures", "category_code": "MJ7"},
            {"name": "Computer Science Practical 3", "category_code": "MJP3"},
            {"name": "Vector Space", "category_code": "Minor"},
            {"name": "PM-3B Vector Spaces", "category_code": "Minor"},
            {"name": "Philosophy of Dr.B.R.Ambedkar", "category_code": "OE"},
            {"name": "Java Programming", "category_code": "VSC"},
            {"name": "हिंदी भाषा व्यवहारिक प्रयोग", "category_code": "AEC"},
            {"name": "Field Project", "category_code": "FP"},
            {"name": "Introduction to Sports Training & Tests and Measurement", "category_code": "Co-Curricular"}
        ]
        
        # Create categories
        category_map = {}
        for cat_data in categories_data:
            # Check if category already exists for this user
            existing = Category.query.filter_by(user_id=user.id, code=cat_data["code"]).first()
            if existing:
                print(f"Category {cat_data['code']} already exists, skipping.")
                category_map[cat_data["code"]] = existing
                continue
            
            category = Category(
                user_id=user.id,
                code=cat_data["code"],
                name=cat_data["name"]
            )
            db.session.add(category)
            category_map[cat_data["code"]] = category
            print(f"Added category: {cat_data['code']} - {cat_data['name']}")
        
        # Commit categories first so we have their IDs
        db.session.commit()
        
        # Create subjects
        for sub_data in subjects_data:
            # Check if subject already exists for this user
            existing = Subject.query.filter_by(user_id=user.id, name=sub_data["name"]).first()
            if existing:
                print(f"Subject '{sub_data['name']}' already exists, skipping.")
                continue
            
            category = category_map.get(sub_data["category_code"])
            subject = Subject(
                user_id=user.id,
                name=sub_data["name"],
                category_id=category.id if category else None
            )
            db.session.add(subject)
            print(f"Added subject: {sub_data['name']} (Category: {sub_data['category_code']})")
        
        db.session.commit()
        print("Done seeding!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        # Default to ramjitesh919@gmail.com as per user's previous messages
        email = "ramjitesh919@gmail.com"
    seed_subjects_for_user(email)
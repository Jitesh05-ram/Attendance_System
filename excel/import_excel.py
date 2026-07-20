import pandas as pd
from datetime import datetime
from database.models import Student
from database.db import db

def import_students_from_file(file_path, user_id, admission_year=None):
    """
    Import students from Excel or CSV file
    
    Args:
        file_path (str): Path to the file
        user_id (int): ID of the current user
        admission_year (int, optional): Admission year to use if not provided in file
        
    Returns:
        tuple: (count of imported students, list of duplicates, list of errors)
    """
    imported_count = 0
    duplicates = []
    errors = []
    
    # Determine file type and read accordingly
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Please use .csv, .xlsx, or .xls")
    
    # Clean up column names (lowercase, strip spaces)
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Find the name column (first try "name", then first column)
    name_col = None
    if 'name' in df.columns:
        name_col = 'name'
    elif len(df.columns) > 0:
        name_col = df.columns[0]
    else:
        errors.append("File has no columns")
        return 0, duplicates, errors
    
    # Get admission year (use provided, or current year)
    if not admission_year:
        admission_year = datetime.today().year
    
    # Process each row
    existing_roll_nos = set([s.roll_no for s in Student.query.filter_by(user_id=user_id).all()])
    
    for index, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name.lower() == 'nan':
            continue
            
        # Generate a roll number if not provided
        roll_no = None
        if 'roll no' in df.columns:
            roll_no = str(row['roll no']).strip()
        elif 'rollno' in df.columns:
            roll_no = str(row['rollno']).strip()
        else:
            # Generate a simple roll number based on index
            roll_no = f"IMP-{user_id}-{index+1}"
        
        if not roll_no or roll_no.lower() == 'nan':
            roll_no = f"IMP-{user_id}-{index+1}"
        
        # Check for duplicates in the imported data
        if roll_no in existing_roll_nos:
            duplicates.append({
                'roll_no': roll_no,
                'name': name
            })
            continue
        
        # Get email if present
        email = None
        if 'email' in df.columns:
            email_val = str(row['email']).strip().lower()
            if email_val and email_val.lower() != 'nan':
                email = email_val
        
        # Create student
        student = Student(
            user_id=user_id,
            roll_no=roll_no,
            name=name,
            admission_year=admission_year,
            email=email
        )
        
        db.session.add(student)
        existing_roll_nos.add(roll_no)
        imported_count += 1
    
    db.session.commit()
    return imported_count, duplicates, errors

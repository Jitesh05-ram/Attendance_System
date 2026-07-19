
from app import app, db
from database.models import User, Student

with app.app_context():
    # Get your user account
    user_email = "ramjitesh919@gmail.com"
    user = User.query.filter_by(email=user_email).first()
    if not user:
        print(f"❌ User {user_email} not found!")
        exit()
    print(f"✅ Found user: {user.name} (ID: {user.id})")
    
    # List of students from the images
    students_list = [
        ("26FCS 1", "ANSARI NAGEEF AHMED JAMIL", "26FCS"),
        ("26FCS 2", "BAKKAR SIRAJ NARESH", "26FCS"),
        ("26FCS 3", "CHAUHAN SONALI VINOD", "26FCS"),
        ("26FCS 4", "DEOGHARKAR AKANKSHA MAHENDRA", "26FCS"),
        ("26FCS 5", "DOKADIA AASIYA MOHAMED IDRISH", "26FCS"),
        ("26FCS 6", "DUBEY AADARSH VINIT", "26FCS"),
        ("26FCS 7", "JAISWAL KASHISH RAMSAMUJ", "26FCS"),
        ("26FCS 8", "KHAN OWAIS KHALID RAZA", "26FCS"),
        ("26FCS 9", "KHAN SAMEER SALIM", "26FCS"),
        ("26FCS 10", "KURLEKAR GAURAV GANESH", "26FCS"),
        ("26FCS 11", "MATAL PRATIK PRAVIN", "26FCS"),
        ("26FCS 12", "PINJARI NAYAF MOHAMAD", "26FCS"),
        ("26FCS 13", "REHAN MD WASI ALAM", "26FCS"),
        ("26FCS 14", "SAYYED KALBE HUSSAIN", "26FCS"),
        ("26FCS 15", "YADAV ANIL DILIP", "26FCS"),
        ("26FCS 16", "YADAV TIRATH ANIL", "26FCS"),
        ("26FCS 17", "PAWAR AARTI SUNIL", "26FCS"),
        ("26FCS 18", "ANSARI AYESHA KHATOON KHURSHID AHMED", "26FCS"),
        ("26FCS 19", "JHA KISHAN BIPIN", "26FCS"),
        ("26FCS 20", "GAWADE TANVI VISHNU", "26FCS"),
        ("26FCS 21", "SHAIKH MOHAMMED ZAID ISMAIL", "26FCS"),
        ("26FCS 22", "PERVE BHAVESH LAVESH", "26FCS"),
        ("26FCS 23", "SHAIKH ALI TANVEER SHAMSHER", "26FCS"),
        ("26FCS 24", "SHAIKH AMAN ALTAF", "26FCS"),
        ("26FCS 25", "MORE ANISHA DNYANESHWAR", "26FCS"),
        ("26FCS 26", "JAISWAR KUNDAN SHESHMANI", "26FCS"),
        ("26FCS 27", "ANSARI SAIF IMAMUDDIN", "26FCS"),
        ("26FCS 28", "KHAN ASIF ARSHAD", "26FCS"),
        ("26FCS 29", "NIGUDKAR HARSH VIJAY", "26FCS"),
        ("26FCS 30", "SHAIKH MAHAMAD FARHAN WAGID HUSSAIN", "26FCS"),
        ("26FCS 31", "SHAIKH MOHO. SULEMAN JAMIL", "26FCS"),
        ("26FCS 32", "PRAJAPATI MAHESH RAJENDRA", "26FCS"),
        ("26FCS 33", "MANIHAR FARHAN SHAMSULLAH", "26FCS"),
        ("26FCS 34", "SHAIKH REHAN NISAR", "26FCS"),
        ("26FCS 35", "MISTRY HUSEN BILAL", "26FCS"),
        ("26FCS 36", "JADHAV JAY SANDEEP", "26FCS"),
        ("26FCS 37", "MARTAL SHLOK SHASHANK", "26FCS"),
        ("26FCS 38", "KOMARAVELLI VIGNESH SRINIVAS", "26FCS"),
        ("26FCS 39", "ANSARI SHOAIB MANJUR", "26FCS"),
        ("26FCS 40", "SHAIKH MOHD TAUHD ZAKIR", "26FCS"),
        ("26FCS 41", "SHARMA PRINCE PRAMOD", "26FCS"),
        ("26FCS 42", "AFJAL PINJARI ALTAMASH", "26FCS"),
        ("26FCS 43", "GUPTA AMAN RAHUL", "26FCS"),
        ("26FCS 44", "SHAH ANAS SARATULLAH", "26FCS"),
        ("26FCS 45", "RAI ANJU SHAILESH", "26FCS"),
        ("26FCS 46", "BACCHE SHIVAM MADAN", "26FCS"),
        ("26FCS 47", "GUPTA ABHAY GANGA PRASAD", "26FCS"),
        ("26FCS 48", "PRAJAPATI ADITYA PRADEEP", "26FCS"),
        ("26FCS 49", "MAURYA ARYAN TRILOKINATH", "26FCS"),
        ("26FCS 50", "TODANKAR SUJAL LAXMAN", "26FCS"),
        ("26FCS 51", "KHAN EBBAN IRFAN", "26FCS"),
        ("26FCS 52", "DUBEY SAURABH VIJAY SHANKAR", "26FCS"),
        ("26FCS 53", "GHORI AMAAN ALI MOHAMMED NIKKI", "26FCS"),
        ("26FCS 54", "SIDDIQUI ARNAAZ GULZAR ALI", "26FCS"),
        ("26FCS 55", "SHAIKH ADIL NASIRUDDIN", "26FCS"),
        ("26FCS 56", "PAGADE VEDANT NARESH", "26FCS"),
        ("26FCS 57", "MORE SHREYAS VIKAS", "26FCS"),
        ("26FCS 58", "SHAIKH MOHAMMED REHAN ZAHIR", "26FCS"),
        ("26FCS 59", "SHAIKH SAHIL MOHD HAMID", "26FCS"),
        ("26FCS 60", "Pal Aryan Ramji", "26FCS")
    ]

    # Add each student to the database
    added_count = 0
    for roll_no, name, class_name in students_list:
        existing_student = Student.query.filter_by(
            user_id=user.id,
            roll_no=roll_no
        ).first()
        if not existing_student:
            # Add user_id and default year
            student = Student(
                user_id=user.id,
                roll_no=roll_no, 
                name=name, 
                class_name=class_name,
                year="FY"  # Default year
            )
            db.session.add(student)
            added_count +=1
            print(f"✅ Added student: {name} ({roll_no})")
        else:
            print(f"ℹ️ Student already exists: {name} ({roll_no})")
    
    db.session.commit()
    print(f"\n✅ Done! {added_count} students added! All assigned to {user_email}!")

import os
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from google.cloud import firestore

class GoogleServices:
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/datastore'
    ]
    
    def __init__(self, service_account_path, spreadsheet_id):
        self.service_account_path = service_account_path
        self.spreadsheet_id = spreadsheet_id
        
        # Load credentials
        self.credentials = Credentials.from_service_account_file(
            service_account_path,
            scopes=self.SCOPES
        )
        
        # Initialize services
        self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
        self.firestore_db = firestore.Client(credentials=self.credentials)
        
        # Sheet tab names (one per year)
        self.SHEET_NAMES = ['FY', 'SY', 'TY']
        self.HEADERS = ['Student Name', 'Roll Number', 'Year', 'Date', 'Attendance Status', 'Timestamp']
        
        # Initialize sheets if they don't exist
        self._initialize_sheets()
    
    def _initialize_sheets(self):
        """Create sheets and headers if they don't exist"""
        try:
            sheet_metadata = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            existing_sheets = [sheet['properties']['title'] for sheet in sheet_metadata['sheets']]
            
            for sheet_name in self.SHEET_NAMES:
                if sheet_name not in existing_sheets:
                    # Create new sheet
                    request_body = {
                        'requests': [{
                            'addSheet': {
                                'properties': {
                                    'title': sheet_name
                                }
                            }
                        }]
                    }
                    self.sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body=request_body
                    ).execute()
                
                # Check if headers exist
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{sheet_name}!A1:F1'
                ).execute()
                
                if 'values' not in result:
                    # Add headers
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'{sheet_name}!A1:F1',
                        valueInputOption='RAW',
                        body={'values': [self.HEADERS]}
                    ).execute()
        except Exception as e:
            print(f"Error initializing sheets: {e}")
    
    def sync_attendance_to_cloud(self, student_name, roll_number, year, date_str, status):
        """Sync attendance to both Firestore and Google Sheets"""
        timestamp = datetime.now().isoformat()
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 1. Save to Firestore
        attendance_doc = {
            'student_name': student_name,
            'roll_number': roll_number,
            'year': year,
            'date': date_obj,
            'status': status,
            'timestamp': timestamp
        }
        # Create a unique ID based on roll number and date
        doc_id = f"{roll_number}_{date_str}"
        self.firestore_db.collection('attendance').document(doc_id).set(attendance_doc)
        
        # 2. Sync to Google Sheets
        self._append_to_sheet(year, [
            student_name,
            roll_number,
            year,
            date_str,
            status,
            timestamp
        ])
        
        return True
    
    def _append_to_sheet(self, year, row_data):
        """Append a row to the appropriate year sheet"""
        try:
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{year}!A:F',
                valueInputOption='RAW',
                body={'values': [row_data]}
            ).execute()
        except Exception as e:
            print(f"Error appending to sheet: {e}")

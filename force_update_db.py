# force_update_db.py
from app import app, db

print("Attempting to update the database structure...")

try:
    with app.app_context():
        # This command only adds missing tables/columns
        db.create_all() 
    print("✅ Success! db.create_all() executed.")
    print("   The 'requester_name' column should now exist if it was missing.")
except Exception as e:
    print("\n❌ An error occurred during db.create_all():")
    print(e)
    print("\n   Make sure NO other program (like the Flask server 'python app.py')")
    print("   is running or accessing the 'site.db' file.")
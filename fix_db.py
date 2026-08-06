from app import app
from models.user import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text('DROP TABLE user_documents'))
        db.session.commit()
        print("Dropped user_documents table")
    except Exception as e:
        print("Error dropping table:", e)
        db.session.rollback()
    
    db.create_all()
    print("Recreated tables successfully")

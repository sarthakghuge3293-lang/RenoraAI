from app import app
from models.user import db, User
from werkzeug.security import generate_password_hash

with app.app_context():

    admin = User.query.filter_by(
        email="admin@renvoratech.com"
    ).first()

    if admin:

        admin.password = generate_password_hash("Admin@123")

        db.session.commit()

        print("✅ Password Reset Successfully!")

    else:

        print("❌ Admin Not Found")
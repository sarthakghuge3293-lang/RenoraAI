import os
from flask import Flask
from config import Config
from models.user import db, User
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    email = "shivcoretech11@gmail.com"
    existing = User.query.filter_by(email=email).first()
    if existing:
        print("User already exists!")
        existing.password = generate_password_hash("Admin.123")
        existing.role = "admin"
        db.session.commit()
        print("Updated existing user.")
    else:
        new_admin = User(
            name="Admin",
            email=email,
            password=generate_password_hash("Admin.123"),
            role="admin"
        )
        db.session.add(new_admin)
        db.session.commit()
        print("Admin user created successfully!")

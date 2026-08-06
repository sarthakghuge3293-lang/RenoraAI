from werkzeug.security import generate_password_hash

from models.user import db, User

from app import app


with app.app_context():

    email = "admin@renvoratech.com"

    check = User.query.filter_by(email=email).first()

    if check:

        print("Super Admin Already Exists")

    else:

        admin = User(

            name="Super Admin",

            email=email,

            password=generate_password_hash("Admin@123"),

            role="super_admin"

        )

        db.session.add(admin)

        db.session.commit()

        print("Super Admin Created Successfully")
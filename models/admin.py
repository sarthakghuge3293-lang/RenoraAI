from config import db


class Admin(db.Model):

    __tablename__ = "admin"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(150), nullable=False)

    username = db.Column(db.String(100), unique=True, nullable=False)

    email = db.Column(db.String(150), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(50), default="Admin")

    status = db.Column(db.String(20), default="Active")

    last_login = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime)

    updated_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Admin {self.username}>"
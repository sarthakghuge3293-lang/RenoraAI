from models.user import db
from datetime import datetime


class ProjectInquiry(db.Model):
    __tablename__ = "project_inquiries"

    id = db.Column(db.Integer, primary_key=True)

    project_type = db.Column(db.String(100), nullable=False)

    project_name = db.Column(db.String(255), nullable=False)

    business_type = db.Column(db.String(255), nullable=False)

    purpose = db.Column(db.Text, nullable=False)

    customer_name = db.Column(db.String(150), nullable=False)

    mobile = db.Column(db.String(20), nullable=False)

    email = db.Column(db.String(150), nullable=False)

    company = db.Column(db.String(255), nullable=False)

    notes = db.Column(db.Text)

    status = db.Column(
        db.String(50),
        default="New"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    
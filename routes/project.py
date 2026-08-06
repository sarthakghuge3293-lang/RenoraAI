from flask import Blueprint, request, jsonify
from models.user import db
from models.project import ProjectInquiry

project = Blueprint("project", __name__)


@project.route("/submit_project", methods=["POST"])
def submit_project():

    try:

        data = request.get_json()

        project_data = ProjectInquiry(

            project_type=data.get("project_type"),

            project_name=data.get("project_name"),

            business_type=data.get("business_type"),

            purpose=data.get("purpose"),

            customer_name=data.get("customer_name"),

            mobile=data.get("mobile"),

            email=data.get("email"),

            company=data.get("company"),

            notes=data.get("notes")

        )

        db.session.add(project_data)

        db.session.commit()

        return jsonify({

            "success": True,

            "message": "Project submitted successfully."

        })

    except Exception as e:

        db.session.rollback()

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500
from flask import Blueprint, render_template, request, redirect, flash
from werkzeug.security import generate_password_hash

from models.user import db, User

setup = Blueprint("setup", __name__)


@setup.route("/setup-super-admin", methods=["GET", "POST"])
def setup_super_admin():

    # Check if Super Admin Already Exists
    admin = User.query.filter_by(role="super_admin").first()

    if admin:
        return "Super Admin Already Exists."

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        new_admin = User(

            name=name,

            email=email,

            password=generate_password_hash(password),

            role="super_admin"

        )

        db.session.add(new_admin)

        db.session.commit()

        flash("Super Admin Created Successfully!", "success")

        return redirect("/admin/login")

    return render_template("setup_super_admin.html")
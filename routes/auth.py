from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import db, User

auth = Blueprint("auth", __name__)

# ==========================================
# Register
# ==========================================
@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if Email Already Exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email already registered!", "danger")
            return redirect(url_for("auth.register"))

        # Hash Password
        hashed_password = generate_password_hash(password)

        # Create User
        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration Successful! Please Login.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ==========================================
# Login
# ==========================================
@auth.route("/login", methods=["GET", "POST"])
def login():

    # Already Logged In
    if "user_id" in session:
        return redirect("/chat")

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        # Find User
        user = User.query.filter_by(email=email).first()

        # Verify Password
        if user and check_password_hash(user.password, password):

            # Create Session
            session["user_id"] = user.id
            session["user_name"] = user.name
            session["user_email"] = user.email

            flash("Welcome Back!", "success")

            return redirect("/chat")

        flash("Invalid Email or Password!", "danger")

    return render_template("login.html")


# ==========================================
# Logout
# ==========================================
@auth.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully!", "success")

    return redirect(url_for("auth.login"))
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import BadSignature, SignatureExpired
from flask_dance.contrib.google import google
from app import db, login_manager, serializer
from .models import User
from .email_utils import send_email
import secrets

# Create a Blueprint for authentication
auth_bp = Blueprint("auth", __name__)

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------------
# Routes
# ------------------------

# Home (protected)
@auth_bp.route("/")
@login_required
def home():
    return render_template("index.html", name=current_user.name)


# Register
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already taken!", "danger")
            return redirect(url_for("auth.register"))

        # Save user with hashed password
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        new_user = User(name=name, email=email, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


# Login
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            flash("Login successful!", "success")
            return redirect(url_for("auth.home"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


# Logout
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# Change password
@auth_bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_pw = request.form.get("current_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        if not check_password_hash(current_user.password, current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("auth.change_password"))

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("auth.change_password"))

        current_user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.session.commit()

        flash("Your password has been updated!", "success")
        return redirect(url_for("auth.account"))

    return render_template("change_password.html")


# Forgot password
@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(user.email, salt="password-reset-salt")
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            body = f"Click the link to reset your password: {reset_url}"
            send_email(user.email, "Password Reset Request", body)
            flash("A reset link has been sent to your email.", "info")
            return redirect(url_for("auth.login"))
        else:
            flash("Email not found.", "danger")

    return render_template("forgot_password.html")


# Reset password
@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except (BadSignature, SignatureExpired):
        flash("The reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if request.method == "POST":
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")

        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.session.commit()

        flash("Your password has been reset. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


# Account
@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        current_user.name = request.form.get("name")
        current_user.username = request.form.get("username")
        current_user.email = request.form.get("email")

        db.session.commit()
        flash("Account updated successfully!", "success")
        return redirect(url_for("auth.account"))

    return render_template("account.html", user=current_user)


# Google login
@auth_bp.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Failed to fetch Google user info", "danger")
        return redirect(url_for("auth.login"))

    user_info = resp.json()
    email = user_info["email"]
    name = user_info.get("name", email.split("@")[0])

    # Check if user already exists
    user = User.query.filter_by(email=email).first()
    if not user:
        new_user = User(
            name=name,
            email=email,
            username=email,
            password=generate_password_hash(secrets.token_hex(16), method="pbkdf2:sha256")
        )
        db.session.add(new_user)
        db.session.commit()
        user = new_user

    login_user(user)
    flash("Logged in with Google!", "success")
    return redirect(url_for("auth.home"))

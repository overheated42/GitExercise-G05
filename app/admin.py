# admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from .models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# -------------------
# ADMIN ACCESS DECORATOR
# -------------------
def admin_required(func):
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            flash("Access denied! Admins only.", "danger")
            return redirect(url_for("auth.home"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# -------------------
# DASHBOARD
# -------------------
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    users = User.query.all()
    total_users = len(users)
    return render_template("admin_dashboard.html", users=users, total_users=total_users)

# -------------------
# EDIT USER
# -------------------
@admin_bp.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        user.name = request.form.get("name")
        user.email = request.form.get("email")
        user.role = request.form.get("role")
        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("edit_user.html", user=user)


# -------------------
# DELETE USER
# -------------------
@admin_bp.route("/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully!", "success")
    return redirect(url_for("admin.dashboard"))

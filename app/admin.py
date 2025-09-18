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
    active_users = User.query.filter_by(is_active=True).count() if hasattr(User, "is_active") else total_users
    return render_template("admin_dashboard.html", users=users, total_users=total_users)

# -------------------
# USER LIST (with search)
# -------------------
@admin_bp.route("/users")
@admin_required
def users():
    search_query = request.args.get("q", "")
    if search_query:
        users_list = User.query.filter(
            (User.username.contains(search_query)) | 
            (User.email.contains(search_query)) | 
            (User.name.contains(search_query))
        ).all()
    else:
        users_list = User.query.all()
    return render_template("admin_users.html", users=users_list, search_query=search_query)


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
        user.is_active = bool(request.form.get("is_active")) if hasattr(user, "is_active") else True
        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("admin.users"))

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


# -------------------
# ACTIVATE / DEACTIVATE USER
# -------------------
@admin_bp.route("/toggle_active/<int:user_id>", methods=["POST"])
@admin_required
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if hasattr(user, "is_active"):
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"User {'activated' if user.is_active else 'deactivated'} successfully!", "success")
    return redirect(url_for("admin.users"))

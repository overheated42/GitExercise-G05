# admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from .models import User , Visit, Location
import json
from sqlalchemy import func
import os


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
        # Get form data
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "").strip()
        is_active = True if request.form.get("is_active") == "on" else False

        # Validation
        if not name:
            flash("Name is required.", "danger")
            return render_template("edit_user.html", user=user)
        if not email:
            flash("Email is required.", "danger")
            return render_template("edit_user.html", user=user)
        if role not in ["admin", "user"]:
            flash("Invalid role selected.", "danger")
            return render_template("edit_user.html", user=user)

        # Update user
        user.name = name
        user.email = email
        user.role = role
        user.is_active = is_active

        try:
            db.session.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for("admin.users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating user: {str(e)}", "danger")
            return render_template("edit_user.html", user=user)

    # GET request
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

from datetime import date
from .models import PageView

@admin_bp.route("/analytics")
@admin_required
def analytics():
    today = date.today()

    # -------------------
    # 1️⃣ Load campus GeoJSON
    # -------------------
    geojson_path = os.path.join(current_app.root_path, "static", "campus_places.geojson")
    campus_geojson = {}
    total_locations = 0
    categories = {"Faculty": 0, "Food": 0, "Facility": 0, "Other": 0}

    if os.path.exists(geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as f:
            campus_geojson = json.load(f)

        total_locations = len(campus_geojson.get("features", []))
        for feature in campus_geojson.get("features", []):
            name = feature["properties"].get("name", "").lower()
            if "faculty" in name:
                categories["Faculty"] += 1
            elif any(x in name for x in ["cafe", "restaurant", "restoran", "bistro"]):
                categories["Food"] += 1
            elif any(x in name for x in ["hall", "library", "surau", "stad", "office", "building", "complex"]):
                categories["Facility"] += 1
            else:
                categories["Other"] += 1

    # -------------------
    # 2️⃣ Most visited locations
    # -------------------
    most_visited = (
        db.session.query(Location.name, func.count(Visit.id).label("visits"))
        .join(Visit)
        .group_by(Location.id)
        .order_by(func.count(Visit.id).desc())
        .all()
    )

    # -------------------
    # 3️⃣ Active users
    # -------------------
    active_users = User.query.filter_by(is_active=True).count()

    # -------------------
    # 4️⃣ Page views today
    # -------------------
    pageviews_today = (
        db.session.query(PageView.page, func.count(PageView.id).label("views"))
        .filter(PageView.view_date == today)
        .group_by(PageView.page)
        .all()
    )

    return render_template(
        "analytics.html",
        total_locations=total_locations,
        categories=categories,
        campus_geojson=campus_geojson,
        most_visited=most_visited,
        active_users=active_users,
        pageviews_today=pageviews_today,
        today=today
    )

# admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from .models import User , Location, Visit, ActivityLog , PageView
import json
from sqlalchemy import func, Date, cast
import os
from datetime import datetime, date, timedelta, time

with open("app/static/campus_places.geojson") as f:  
    campus_places = json.load(f)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

GEOJSON_PATH = os.path.join("app", "static", "campus_places.geojson")


def log_activity(action, user=None):
    entry = ActivityLog(action=action)
    if user:
        entry.user = user
    db.session.add(entry)
    db.session.commit()

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
    log_activity("Viewed Admin Dashboard", user=current_user)

    users = User.query.all()
    total_users = len(users)
    active_users = User.query.filter_by(is_active=True).count() if hasattr(User, "is_active") else total_users

    popular_locations = (
        db.session.query(Location.name, func.count(Visit.id).label("visits"))
        .join(Visit)
        .group_by(Location.id)
        .order_by(func.count(Visit.id).desc())
        .limit(3)
        .all()
    )
    popular_locations = [loc[0] for loc in popular_locations]

    # Fetch last 10 activities
    recent_activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()

    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)

    user_growth = (
        db.session.query(func.date(User.created_at), func.count(User.id))
        .filter(User.created_at >= seven_days_ago)
        .group_by(func.date(User.created_at))
        .all()
    )

    # Format into dict {date: count}
    growth_dict = {str(date): count for date, count in user_growth}

    labels = [(seven_days_ago + timedelta(days=i)).strftime("%a") for i in range(7)]  # Mon, Tue...
    data = [growth_dict.get(str(seven_days_ago + timedelta(days=i)), 0) for i in range(7)]


    return render_template(
        "admin_dashboard.html",
        users=users,
        total_users=total_users,
        active_users=active_users,
        recent_activities=recent_activities,
        popular_locations=popular_locations,
        growth_labels=json.dumps(labels),   # ✅ Pass to JS safely
        growth_data=json.dumps(data)
    )
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
            log_activity(f"Edited user {user.username}", user=current_user)
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
    log_activity(f"Deleted user {user.username}", user=current_user)
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
        log_activity(f"{'Activated' if user.is_active else 'Deactivated'} user {user.username}", user=current_user)
    return redirect(url_for("admin.users"))

from datetime import date
from .models import PageView

@admin_bp.route("/analytics")
@admin_required
def analytics():
    log_activity("Viewed Analytics Page", user=current_user)

    today = date.today()
    start = datetime.combine(today, time.min)  # 00:00:00
    end = datetime.combine(today, time.max)    

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
        .filter(PageView.timestamp >= start, PageView.timestamp <= end)
        .group_by(PageView.page)
        .all()
    )

    page_labels = [p[0] for p in pageviews_today]
    page_counts = [p[1] for p in pageviews_today]

    return render_template(
        "analytics.html",
        total_locations=total_locations,
        categories=categories,
        campus_geojson=campus_geojson,
        campus_places=campus_geojson,  
        most_visited=most_visited,
        active_users=active_users,
        pageviews_today=pageviews_today,
        page_labels=page_labels,       # ✅ new
        page_counts=page_counts,       # ✅ new
        today=today
    )

@admin_bp.route("/log_visit", methods=["POST"])
def log_visit():
    data = request.get_json()
    location_name = data.get("location")

    if not location_name:
        return jsonify({"error": "No location provided"}), 400

    # find or create the location in DB
    location = Location.query.filter_by(name=location_name).first()
    if not location:
        location = Location(name=location_name)
        db.session.add(location)
        db.session.commit()

    # log visit
    visit = Visit(user_id=current_user.id if current_user.is_authenticated else None,
                  location_id=location.id,
                  timestamp=datetime.utcnow())
    db.session.add(visit)
    db.session.commit()

    return jsonify({"message": "Visit logged"}), 200

@admin_bp.route("/locations", methods=["GET", "POST"])
def edit_locations():
    if request.method == "POST":
        # Save updated GeoJSON from frontend
        updated_geojson = request.json
        with open(GEOJSON_PATH, "w", encoding="utf-8") as f:
            json.dump(updated_geojson, f, indent=2)
        return {"status": "success"}

    # GET: load locations from file
    if os.path.exists(GEOJSON_PATH):
        with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)
    else:
        geojson_data = {"type": "FeatureCollection", "features": []}

    return render_template("edit_locations.html", locations=geojson_data)
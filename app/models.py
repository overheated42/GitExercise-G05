from . import db, login_manager
from flask_login import UserMixin
from datetime import datetime, date


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default="user")  # 'user' or 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # NEW: track registration

    visits = db.relationship("Visit", backref="user", lazy=True)
    pageviews = db.relationship("PageView", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    category = db.Column(db.String(50))  # Faculty, Food, Facility, etc.
    latitude = db.Column(db.Float, nullable=True)   # Add this
    longitude = db.Column(db.Float, nullable=True)
    visits = db.relationship("Visit", backref="location", lazy=True)

    def __repr__(self):
        return f"<Location {self.name}>"


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    visit_date = db.Column(db.Date, default=date.today)  # for daily aggregation

    def __repr__(self):
        return f"<Visit User:{self.user_id} Location:{self.location_id}>"


class PageView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user_ip = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    view_date = db.Column(db.Date, default=date.today)

    def __repr__(self):
        return f"<PageView {self.page}>"


class ActivityLog(db.Model):
    """Track recent admin & user activities for dashboard feed"""
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(255), nullable=False)  # e.g., 'User registered', 'Route updated'
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="activities")

    def __repr__(self):
        return f"<ActivityLog {self.action} at {self.timestamp}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

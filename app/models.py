from . import db, login_manager
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default="user")  # 'user' or 'admin'
    is_active = db.Column(db.Boolean, default=True)  # <--- make it a real column

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


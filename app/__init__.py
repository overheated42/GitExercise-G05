import os, secrets
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from flask_dance.contrib.google import make_google_blueprint
from datetime import datetime, date

load_dotenv()

if os.getenv("FLASK_ENV") == "development":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY", secrets.token_hex(32)))


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # -------------------
    # Config
    # -------------------
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", secrets.token_hex(32))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER", app.config['MAIL_USERNAME'])

    # -------------------
    # Initialize extensions
    # -------------------
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # -------------------
    # Google OAuth
    # -------------------
    google_bp = make_google_blueprint(
        client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        redirect_to="auth.google_login",
        scope=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email"
        ]
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # -------------------
    # Register Blueprints
    # -------------------
    from .auth import auth_bp
    from .routes import main
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main)
    app.register_blueprint(admin_bp)

    # -------------------
    # Pageview logging
    # -------------------
    @app.before_request
    def log_pageview():
        if request.endpoint not in ("static", None):
            try:
                from .models import PageView

                pageview = PageView(
                    page=request.path,
                    view_date=date.today(),
                    user_id=current_user.id if current_user.is_authenticated else None,
                    user_ip=request.remote_addr
                )
                db.session.add(pageview)
                db.session.commit()
                print(f"Logged pageview: {request.path}")
            except Exception as e:
                db.session.rollback()
                print(f"Pageview logging failed: {e}")

    # -------------------
    # Create tables
    # -------------------
    with app.app_context():
        db.create_all()

    return app

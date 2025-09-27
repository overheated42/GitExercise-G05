import os
import secrets
from datetime import datetime, date
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from flask_dance.contrib.google import make_google_blueprint


# Load environment variables
load_dotenv()

# Allow insecure transport in development
if os.getenv("FLASK_ENV") == "development":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# -------------------
# Extensions
# -------------------
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
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # SQLite concurrency tweak (dev only)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"check_same_thread": False}
    }

    # Mail config
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
    # Pageview Logging
    # -------------------
    @app.before_request
    def log_pageview():
        # Skip static files & favicon
        if request.endpoint in ("static", None) or request.path.startswith("/favicon"):
            return

        try:
            from .models import PageView

            pageview = PageView(
                page=request.path,
                timestamp=datetime.utcnow(),
                view_date=date.today(),
                user_id=current_user.id if current_user.is_authenticated else None,
                user_ip=request.remote_addr
            )
            db.session.add(pageview)
            db.session.commit()
            print(f"✅ Logged pageview: {request.path}")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Pageview logging failed: {e}")

    # -------------------
    # Create DB tables
    # -------------------
    with app.app_context():
        db.create_all()
        
        from .models import User
        from werkzeug.security import generate_password_hash

        existing_admin = User.query.filter_by(username="admin").first()
        if existing_admin:
            existing_admin.name = "Administrator"
            existing_admin.email = "admin@example.com"
            existing_admin.password = generate_password_hash("admin123")
            existing_admin.role = "admin"
            db.session.commit()
            print("✅ Admin user overwritten")
        else:
            default_admin = User(
                name="Administrator",
                username="admin",
                email="admin@example.com",
                password=generate_password_hash("admin123"),
                role="admin"
            )
            db.session.add(default_admin)
            db.session.commit()
            print("✅ Admin user created")

    return app

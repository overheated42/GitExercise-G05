from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import secrets
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv


load_dotenv()

# Allow insecure transport only in debug mode (local development)
if os.getenv("FLASK_ENV") == "development":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Flask app and database 
app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

# Flask-Mail setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")  # your Gmail
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")  # your Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER", app.config['MAIL_USERNAME'])

mail = Mail(app)


db = SQLAlchemy(app)
#Token serialiser
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Google OAuth setup
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
    redirect_to="google_login",   # after login, go here
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
)
app.register_blueprint(google_bp, url_prefix="/login")


#flask-mail helper function
def send_email(to, subject, body):
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        mail.send(msg)
        print(f"Email sent to {to}")
    except Exception as e:
        print(f"Error sending email: {e}")
        if app.debug:
            print(f"Reset link for {to}: {body}")  # fallback in debug mode


# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # store hashed password


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home (protected)
@app.route('/')
@login_required
def home():
    return render_template("index.html", name=current_user.name)

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get("name")
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validation
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already taken!", "danger")
            return redirect(url_for("register"))

        # Save user with hashed password
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        new_user = User(name=name, email=email, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# Change password 
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        # 1. Check old password
        if not check_password_hash(current_user.password, current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('change_password'))

        # 2. Check new passwords match
        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('change_password'))

        # 3. Update password
        current_user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")

        db.session.commit()

        flash("Your password has been updated!", "success")
        return redirect(url_for('account')) # not yet decided where to redirect

    return render_template("change_password.html")

# Forgot password route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            body = f"Click the link to reset your password: {reset_url}"
            send_email(user.email, "Password Reset Request", body)
            flash("A reset link has been sent to your email.", "info")
            return redirect(url_for('login'))
        else:
            flash("Email not found.", "danger")

    return render_template("forgot_password.html")

# Reset password route
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiry
    except:
        flash("The reset link is invalid or expired.", "danger")
        return redirect(url_for('forgot_password'))

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.session.commit()

        flash("Your password has been reset. Please login.", "success")
        return redirect(url_for('login'))

    return render_template("reset_password.html", token=token)

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("email")

        # Update user info
        current_user.username = username
        current_user.email = email
        current_user.name = name

        db.session.commit()
        flash("Account updated successfully!", "success")
        return redirect(url_for("account"))

    return render_template("account.html", user=current_user)

@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Failed to fetch Google user info", "danger")
        return redirect(url_for("login"))

    user_info = resp.json()
    email = user_info["email"]
    name = user_info.get("name", email.split("@")[0])

    # Check if user already exists
    user = User.query.filter_by(email=email).first()
    if not user:
        # create a new user
        new_user = User(
            name=name,
            email=email,
            username=email,  # you could use email as username
            password=generate_password_hash(secrets.token_hex(16), method="pbkdf2:sha256") # random password, unused
        )
        db.session.add(new_user)
        db.session.commit()
        user = new_user

    login_user(user)
    flash("Logged in with Google!", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

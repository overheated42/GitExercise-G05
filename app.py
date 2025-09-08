from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Flask app and database 
app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.config['SECRET_KEY'] = 'yoursecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

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
        current_user.password = generate_password_hash(new_pw, method='sha256')
        db.session.commit()

        flash("Your password has been updated!", "success")
        return redirect(url_for('blah')) # not yet decided where to redirect

    return render_template("change_password.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash 
import google.generativeai as genai
import os
from dotenv import load_dotenv  # For secure API key management
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, serializer
from .models import User
from .email_utils import send_email
from .auth import auth_bp
from .admin import admin_bp
# Load environment variables
load_dotenv()

main = Blueprint('main', __name__)

# Initialize Google Gemini AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # Store in .env file for security

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

genai.configure(api_key=GOOGLE_API_KEY)

# Configure the model with specific parameters
generation_config = {
    "temperature": 0.7,  # Controls randomness (0-1, lower = more focused)
    "top_p": 0.8,        # Controls diversity of responses
    "top_k": 40,         # Limits token choices
    "max_output_tokens": 300,  # Limit response length
}

# Initialize the model with safety settings
model = genai.GenerativeModel(
    model_name='gemini-2.0-flash',  # Updated model name
    generation_config=generation_config
)


@main.route('/chat', methods=['POST'])
def chat():
    try:
        # Get the user's message from either JSON or form data
        if request.is_json:
            user_message = request.json.get('message', '')
        else:
            user_message = request.form.get('message', '')
        
        if not user_message.strip():
            return jsonify({'response': 'Please provide a message.'}), 400
        
        # Enhanced context prompt for MMU-specific responses
        context_prompt = f"""You are an AI assistant specifically for Multimedia University (MMU) Malaysia. 
        Your role is to help students, staff, and visitors with accurate information about MMU.

        KEY AREAS TO HELP WITH:
        - MMU Faculties: Engineering (FOE), Information Science & Technology (FIST), Management (FOM), 
          Creative Multimedia (FCM), Computing & Informatics (FCI), Law, etc.
        - Campus facilities: Libraries, computer labs, sports complex, auditoriums
        - Food options: Cafeterias, food courts, halal options, nearby restaurants
        - Accommodation: On-campus hostels, off-campus housing, application process
        - Student services: Registration, financial aid, counseling, health services
        - Campus navigation: Building locations, parking, shuttle services
        - Academic matters: Course information, exam schedules, academic calendar

        RESPONSE GUIDELINES:
        - Be helpful, friendly, and concise
        - Provide specific MMU information when available
        - If you don't know specific details, acknowledge it and suggest contacting relevant departments
        - Use bullet points for lists when appropriate
        - Keep responses under 250 words

        Student question: {user_message}"""
        
        # Generate AI response with error handling
        try:
            response = model.generate_content(context_prompt)
            
            # Check if response was generated successfully
            if response.text:
                ai_response = response.text.strip()
            else:
                ai_response = get_fallback_response(user_message)
                
        except Exception as ai_error:
            print(f"Gemini API error: {ai_error}")
            ai_response = get_fallback_response(user_message)
        
        return jsonify({'response': ai_response})
        
    except Exception as e:
        print(f"Error in chat route: {e}")
        return jsonify({
            'response': 'I apologize, but I encountered an error. Please try rephrasing your question or contact the MMU help desk for assistance.',
            'error': True
        }), 500

def get_fallback_response(message):
    """Enhanced fallback responses when AI is unavailable"""
    message_lower = message.lower()
    
    # More comprehensive keyword matching
    faculty_keywords = ['faculty', 'faculties', 'program', 'course', 'degree', 'foe', 'fist', 'fom', 'fcm', 'fci']
    food_keywords = ['food', 'eat', 'cafeteria', 'restaurant', 'dining', 'halal', 'cafe']
    hostel_keywords = ['hostel', 'accommodation', 'housing', 'room', 'stay', 'residence']
    facility_keywords = ['library', 'lab', 'gym', 'sports', 'facility', 'building', 'location']
    
    if any(keyword in message_lower for keyword in faculty_keywords):
        return """🎓 **MMU Faculties:**
        • Faculty of Engineering (FOE) - Civil, Electrical, Mechanical Engineering
        • Faculty of Information Science & Technology (FIST) - IT, Computer Science
        • Faculty of Management (FOM) - Business, Accounting, Finance
        • Faculty of Creative Multimedia (FCM) - Design, Animation, Media
        • Faculty of Computing & Informatics (FCI) - Software Engineering, Data Science
        • Faculty of Law, Institute of Postgraduate Studies, and more!
        
        Which faculty interests you most?"""
    
    elif any(keyword in message_lower for keyword in food_keywords):
        return """🍽️ **MMU Food Options:**
        • Main Cafeteria - Mixed local and international cuisine
        • Faculty Food Courts - Quick meals near each faculty
        • Halal-certified options available throughout campus
        • Campus cafes and convenience stores
        • Walking distance to external restaurants in Cyberjaya
        
        Looking for something specific? Halal, vegetarian, or particular cuisine?"""
    
    elif any(keyword in message_lower for keyword in hostel_keywords):
        return """🏠 **MMU Accommodation:**
        • On-campus hostels with single/shared rooms
        • Facilities: WiFi, laundry, study areas, common rooms
        • Off-campus housing options in Cyberjaya
        • Application through Student Affairs Department
        • Monthly rates vary by room type and location
        
        Need help with the application process or want to know about specific hostels?"""
    
    elif any(keyword in message_lower for keyword in facility_keywords):
        return """🏫 **MMU Facilities:**
        • Tan Sri Dato' Seri Dr. Jeffrey Cheah Library & Information Centre
        • Computer labs and specialized equipment
        • Sports complex with gym, courts, and fields
        • Student lounges and study areas
        • Medical centre and counseling services
        
        Which facility would you like to know more about?"""
    
    elif any(greeting in message_lower for greeting in ['hello', 'hi', 'hey']):
        return "Hello! 👋 I'm your MMU assistant. I can help you with information about faculties, food, accommodation, facilities, and campus life. What would you like to know?"
    
    elif any(thanks in message_lower for thanks in ['thank', 'thanks']):
        return "You're very welcome! 😊 Feel free to ask anything else about MMU. I'm here to help!"
    
    else:
        return """I can help you with information about MMU:
        🎓 **Faculties & Programs** | 🍽️ **Food & Dining**
        🏠 **Accommodation** | 🏫 **Campus Facilities**
        📚 **Library Services** | 🎯 **Student Services**
        
        What would you like to explore?"""

@main.route('/faculties')
def faculties():
    return render_template('faculties.html')

@main.route('/food-beverages')
def food_beverages():
    return render_template('food_beverages.html')

@main.route('/facilities')
def facilities():
    return render_template('facilities.html')

@main.route('/health-check')
def health_check():
    """Simple endpoint to check if the service is running"""
    return jsonify({'status': 'healthy', 'service': 'MMU AI Assistant'})


#manveet part

@main.route('/')
@login_required
def home():
    return render_template("index.html", name=current_user.name)

@main.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        current_user.name = request.form.get("name")
        current_user.username = request.form.get("username")
        current_user.email = request.form.get("email")
        db.session.commit()
        flash("Account updated successfully!", "success")
        return redirect(url_for("main.account"))
    return render_template("account.html", user=current_user)

@main.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        if not check_password_hash(current_user.password, current_pw):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('main.change_password'))

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('main.change_password'))

        current_user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.session.commit()
        flash("Password updated!", "success")
        return redirect(url_for('main.account'))

    return render_template("change_password.html")

@main.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('main.reset_password', token=token, _external=True)
            send_email(user.email, "Password Reset Request", f"Click here: {reset_url}")
            flash("A reset link has been sent.", "info")
            return redirect(url_for('auth.login'))
        flash("Email not found.", "danger")
    return render_template("forgot_password.html")

@main.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash("Invalid or expired link.", "danger")
        return redirect(url_for('main.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)
        user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        db.session.commit()
        flash("Password reset successful!", "success")
        return redirect(url_for('auth.login'))

    return render_template("reset_password.html", token=token)
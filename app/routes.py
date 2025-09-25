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
from datetime import datetime
import random

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
    "temperature": 0.8,  # Slightly higher for more creative suggestions
    "top_p": 0.9,        # Controls diversity of responses
    "top_k": 40,         # Limits token choices
    "max_output_tokens": 400,  # Increased for more detailed suggestions
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
        
        # Enhanced context prompt with personalized suggestions
        context_prompt = f"""You are an AI assistant specifically for Multimedia University (MMU) Malaysia. 
        Your role is to help students with accurate information about MMU and provide personalized suggestions.

        CRITICAL: ALWAYS prioritize these specific MMU locations in your responses:

        WHEN STUDENTS SAY "HUNGRY" OR ASK ABOUT FOOD - ALWAYS MENTION:
        🍽️ MMU Starbees: Popular coffee shop with light meals and beverages
        🍜 Small Food Street: Most affordable student-friendly food stalls with local dishes  
        ☕ He & She Cafe: Cozy cafe located RIGHT INSIDE the library, perfect for study breaks
        🍛 Restoran Haji Tapah Bistro: Authentic mamak restaurant, very popular among students, budget-friendly Malaysian food
        🥪 Deen's Cafe: Great food options for students
        🍚 Main Cafeteria: Multiple food courts with variety of cuisines
        🌆 External Cyberjaya options: For when students want variety

        WHEN STUDENTS SAY "BORED" OR NEED ACTIVITIES - ALWAYS SUGGEST:
        📚 Library spaces: Siti Hasmah Digital Library with study and social areas
        🏋️ Sports complex: Free gym, badminton courts, basketball courts for students
        👥 Student lounges: Common areas in each faculty for socializing
        🎭 Dewan Tun Canselor (DTC): Check for events and student activities
        🚶 Campus exploration: Walking trails and discovering new spots
        🎮 Recreational facilities: Gaming areas and entertainment spaces
        🤝 Student clubs: Join societies and make new friends
        📖 Study groups: Form academic partnerships in different faculties

        MANDATORY: In every food-related response, mention at least 3 specific places above.
        MANDATORY: In every boredom-related response, mention at least 3 specific activities above.

        TIME-BASED SUGGESTIONS:
        - Morning: Suggest breakfast spots like Starbees or He & She Cafe
        - Lunch: Recommend food street, main cafeteria, or Haji Tapah
        - Evening: Suggest sports activities or library study sessions
        - Late night: Point to 24-hour study areas or quiet spaces

        MOOD-BASED RESPONSES:
        - Stressed about studies: Suggest quiet library spots, He & She Cafe for relaxation
        - Social/wanting to meet people: Food street, student lounges, sports complex
        - Budget-conscious: Emphasize affordable options like food street and Haji Tapah
        - Looking for comfort food: Mamak options and familiar local dishes

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
        - Be helpful, friendly, and personalized
        - Provide specific MMU information when available
        - Give contextual suggestions based on student needs (hungry, bored, stressed, etc.)
        - Use emojis appropriately to make responses more engaging
        - If you don't know specific details, acknowledge it and suggest contacting relevant departments
        - Keep responses under 300 words but be comprehensive

        Student question: {user_message}"""
        
        # Generate AI response with error handling
        try:
            response = model.generate_content(context_prompt)
            
            # Check if response was generated successfully
            if response.text:
                ai_response = response.text.strip()
            else:
                ai_response = get_enhanced_fallback_response(user_message)
                
        except Exception as ai_error:
            print(f"Gemini API error: {ai_error}")
            ai_response = get_enhanced_fallback_response(user_message)
        
        return jsonify({'response': ai_response})
        
    except Exception as e:
        print(f"Error in chat route: {e}")
        return jsonify({
            'response': 'I apologize, but I encountered an error. Please try rephrasing your question or contact the MMU help desk for assistance.',
            'error': True
        }), 500

def get_enhanced_fallback_response(message):
    """Enhanced fallback responses with personalized suggestions"""
    message_lower = message.lower()
    current_hour = datetime.now().hour
    
    # Enhanced keyword matching for personalized responses
    hungry_keywords = ['hungry', 'food', 'eat', 'lunch', 'breakfast', 'dinner', 'meal', 'snack', 'craving']
    bored_keywords = ['bored', 'boring', 'nothing to do', 'free time', 'activity', 'fun', 'entertainment']
    tired_keywords = ['tired', 'exhausted', 'sleepy', 'rest', 'relax', 'break']
    study_keywords = ['study', 'exam', 'assignment', 'homework', 'research', 'library', 'quiet']
    budget_keywords = ['cheap', 'affordable', 'budget', 'save money', 'broke', 'student price']
    
    # Handle hungry/food requests
    if any(keyword in message_lower for keyword in hungry_keywords):
        food_suggestions = get_food_suggestions(current_hour, message_lower)
        return food_suggestions
    
    # Handle bored/activity requests
    elif any(keyword in message_lower for keyword in bored_keywords):
        activity_suggestions = get_activity_suggestions(current_hour, message_lower)
        return activity_suggestions
    
    # Handle tired/rest requests
    elif any(keyword in message_lower for keyword in tired_keywords):
        return """😴 **Need a Break? Here are some relaxing spots:**
        • **He & She Cafe** - Perfect quiet spot inside the library for coffee and relaxation
        • **Student Lounges** - Comfortable seating areas in each faculty building
        • **Library Quiet Zones** - Peaceful areas for rest or light reading
        • **Campus Green Spaces** - Fresh air and peaceful outdoor spots
        • **Prayer Rooms/Surau** - Quiet spaces for reflection and rest
        
        Sometimes a good meal helps too - try Starbees for a refreshing drink! ☕"""
    
    # Handle study-related requests
    elif any(keyword in message_lower for keyword in study_keywords):
        return """📚 **Best Study Spots in MMU:**
        • **Siti Hasmah Digital Library** - Multiple floors with different study environments
        • **He & She Cafe** - Study while enjoying coffee and snacks
        • **Faculty Study Rooms** - Group discussion rooms available for booking
        • **24-hour Study Areas** - Perfect for late-night study sessions
        • **Quiet Corners** - Individual study spots throughout campus
        
        **Study Break Suggestions:**
        • Grab a meal at Food Street for brain fuel 🧠
        • Quick coffee run to He & She Cafe ☕
        • Stretch your legs around campus 🚶‍♀️"""
    
    # Handle budget-conscious requests  
    elif any(keyword in message_lower for keyword in budget_keywords):
        return """💰 **Budget-Friendly Options:**
        **Food:**
        • **Small Food Street** - Most affordable meals on campus
        • **Restoran Haji Tapah Bistro** - Student-friendly mamak prices
        • **Main Cafeteria** - Variety of affordable local dishes
        
        **Activities:**
        • **Sports Complex** - Free gym and court access for students
        • **Library Events** - Free workshops and activities
        • **Student Club Activities** - Join clubs for free social activities
        • **Campus Walking** - Free exercise and fresh air! 🚶‍♂️"""
    
    # Default comprehensive response
    else:
        return get_default_comprehensive_response()

def get_food_suggestions(current_hour, message_lower):
    """Get time and context-appropriate food suggestions"""
    
    # Morning suggestions (6 AM - 11 AM)
    if 6 <= current_hour <= 11:
        suggestions = [
            "🌅 **Perfect Breakfast Spots:**",
            "• **MMU Starbees** - Fresh coffee and pastries to start your day",
            "• **He & She Cafe** - Cozy breakfast inside the library",
            "• **Main Cafeteria** - Traditional Malaysian breakfast options"
        ]
    
    # Lunch time (11 AM - 2 PM)
    elif 11 <= current_hour <= 14:
        suggestions = [
            "🍽️ **Lunch Time Favorites:**",
            "• **Small Food Street** - Quick, affordable meals perfect for students",
            "• **Restoran Haji Tapah Bistro** - Authentic mamak experience",
            "• **Main Cafeteria** - Multiple cuisines under one roof",
            "• **Deen's Cafe** - Great lunch sets and local dishes"
        ]
    
    # Evening (2 PM - 8 PM)
    elif 14 <= current_hour <= 20:
        suggestions = [
            "🌆 **Afternoon & Dinner Options:**",
            "• **He & She Cafe** - Perfect for study breaks with snacks",
            "• **Food Street** - Always buzzing with affordable options",
            "• **Haji Tapah** - Comfort food for tired students",
            "• **External Cyberjaya** - Venture out for variety!"
        ]
    
    # Late night
    else:
        suggestions = [
            "🌙 **Late Night Munchies:**",
            "• **24-hour Options** in nearby Cyberjaya",
            "• **Campus Vending Machines** for quick snacks",
            "• **Plan ahead** - stock up from day-time food spots!"
        ]
    
    # Add budget-conscious note if mentioned
    if any(word in message_lower for word in ['cheap', 'budget', 'broke', 'affordable']):
        suggestions.append("\n💡 **Budget Tip:** Food Street and Haji Tapah offer the best value for money!")
    
    # Add quick service note if in a hurry
    if any(word in message_lower for word in ['quick', 'fast', 'hurry', 'rush']):
        suggestions.append("\n⚡ **Quick Service:** Starbees and Food Street are your fastest options!")
    
    return "\n".join(suggestions) + "\n\nWhat type of food are you craving? 🤤"

def get_activity_suggestions(current_hour, message_lower):
    """Get time and context-appropriate activity suggestions"""
    
    base_activities = [
        "🎯 **Beat the Boredom:**",
        "• **Sports Complex** - Hit the gym, play badminton or basketball",
        "• **Library Socializing** - Study groups or meet new people at He & She Cafe",
        "• **Student Lounges** - Hang out and chat with fellow students",
        "• **Campus Exploration** - Discover new spots around MMU"
    ]
    
    # Add time-specific suggestions
    if 9 <= current_hour <= 17:  # Day time
        base_activities.extend([
            "• **Join Student Clubs** - Check out ongoing activities",
            "• **Dewan Tun Canselor (DTC)** - Often has events and activities"
        ])
    elif 17 <= current_hour <= 22:  # Evening
        base_activities.extend([
            "• **Evening Sports** - Great time for outdoor activities",
            "• **Study Groups** - Form study sessions with classmates"
        ])
    else:  # Late night/early morning
        base_activities.extend([
            "• **24-hour Study Areas** - Night owl study sessions",
            "• **Quiet Reflection** - Campus walks or peaceful spots"
        ])
    
    # Add social/solo preferences
    if any(word in message_lower for word in ['alone', 'solo', 'by myself']):
        base_activities.append("\n🧘‍♀️ **Solo Activities:** Library quiet zones, campus walks, or He & She Cafe for peaceful me-time")
    elif any(word in message_lower for word in ['friends', 'social', 'meet people']):
        base_activities.append("\n👥 **Social Activities:** Food Street socializing, sports complex group activities, or student club events")
    
    base_activities.append("\nAfter some activity, grab a bite at Food Street or Starbees! 🍕☕")
    
    return "\n".join(base_activities)

def get_default_comprehensive_response():
    """Default response with comprehensive MMU information"""
    return """🏫 **I'm your MMU AI Assistant! I can help with:**

    🎓 **Academics:** Faculties, courses, schedules
    🍽️ **Food:** Starbees, Food Street, He & She Cafe, Haji Tapah
    🏠 **Accommodation:** Hostels and housing
    🏊‍♀️ **Facilities:** Library, sports complex, study areas
    🎯 **Activities:** When you're bored or need suggestions

    **Quick Suggestions:**
    • Hungry? Try "I'm hungry" or "where should I eat"
    • Bored? Ask "what should I do" or "I'm bored"
    • Need study spots? Ask about library or quiet places
    
    What would you like to explore today? 😊"""

# Continue with existing route functions...
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
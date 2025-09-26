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
import re

# Load environment variables
load_dotenv()

main = Blueprint('main', __name__)

# Initialize Google Gemini AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

genai.configure(api_key=GOOGLE_API_KEY)

# Configure the model with more creative parameters
generation_config = {
    "temperature": 1.0,  # Higher for more creativity and variation
    "top_p": 0.95,       # Higher for more diverse responses
    "top_k": 50,         # More token choices for variety
    "max_output_tokens": 500,  # Longer responses when needed
}
try:
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        generation_config=generation_config
    )

except Exception as e:
    print(f"gemini-2.0-flash error: {e}. Falling back to gemini-1.5-flash.")
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config=generation_config
    )

# MMU Venue Code Parser - Based on official MMU venue code format
def parse_venue_code(venue_code):
    """
    Parse MMU venue codes according to the official format:
    [Campus][Building][Wing][Type] [Floor][Room Number]
    Example: CLCR 2045 = Cyberjaya Campus, FOE, Wing C, Second floor, room 045
    Example: CNMX 1001 = Cyberjaya Campus, CLC, Main area theatre, first floor, room 001
    """
    venue_code = venue_code.upper().strip().replace(' ', '')
    
    # Only Cyberjaya campus (as requested)
    campus_map = {
        'C': 'Cyberjaya Campus'
    }
    
    # Building mapping (2nd alphabet)
    building_map = {
        'J': 'FCM (Faculty of Creative Multimedia)',
        'L': 'FOE (Faculty of Engineering)', 
        'N': 'CLC (Cyberjaya Learning Centre)',
        'Q': 'FCI (Faculty of Computing and Informatics)',
        'R': 'FOM (Faculty of Management)'
    }
    
    # Wing mapping (3rd alphabet)
    wing_map = {
        'M': 'Main Area',
        'A': 'Wing A',
        'B': 'Wing B', 
        'C': 'Wing C'
    }
    
    # Type mapping (4th alphabet)
    type_map = {
        'R': 'Room',
        'X': 'Theatre'
    }
    
    # Floor mapping (1st number)
    floor_map = {
        '0': 'Ground Floor',
        '1': 'First Floor',
        '2': 'Second Floor',
        '3': 'Third Floor'
    }

    # NEW: Hardcoded tips per building (adds flavor—edit/remove as needed)
    building_tips = {
        'FOE (Faculty of Engineering)': 'Engineering central—labs and WiFi are top-notch, but stairs get crowded!',
        'FCI (Faculty of Computing and Informatics)': 'IT/computing hub—great for coding sessions, strong AC too.',
        'FOM (Faculty of Management)': 'Business spot—quiet lounges for presentations.',
        'FCM (Faculty of Creative Multimedia)': 'Creative vibes—art supplies nearby if needed.',
        'CLC (Cyberjaya Learning Centre)': 'Central learning area—easy access from main gate.'
         }
    
    try:
    # Parse the venue code (format: CLCR2045)
        if len(venue_code) >= 7:
            campus = campus_map.get(venue_code[0], 'Cyberjaya Campus')  # Default to Cyberjaya
            building = building_map.get(venue_code[1], 'Unknown Building')
            wing = wing_map.get(venue_code[2], 'Unknown Wing')
            room_type = type_map.get(venue_code[3], 'Unknown Type')
            floor = floor_map.get(venue_code[4], 'Unknown Floor')
            room_number = venue_code[5:].zfill(3) # Ensure room number is 3 digits
            
    # Your format: "FOE, Wing C, Second Floor, Room 045"
        full_location = f"{building}, {wing}, {floor}, {room_type} {room_number}"
            
        return {
                'campus': campus,
                'building': building,
                'wing': wing,
                'type': room_type,
                'floor': floor,
                'room_number': room_number,
                'full_location': f"{building}, {wing}, {floor}, {room_type} {room_number}"
            }
    except:
        pass
    
    return None

@main.route('/chat', methods=['POST'])
def chat():
    try:
        # Get the user's message
        if request.is_json:
            user_message = request.json.get('message', '')
        else:
            user_message = request.form.get('message', '')
        
        if not user_message.strip():
            return jsonify({'response': 'Hey, I need something to work with here! What\'s on your mind?'}), 400
        
        # Check for venue code queries FIRST
        venue_response = handle_venue_query(user_message)
        if venue_response:
            return jsonify({'response': venue_response})
        
        # Enhanced context prompt for more natural conversation
        context_prompt = f"""You are Queen Elizabeth III, a friendly AI assistant who's like a knowledgeable senior student at Multimedia University (MMU) Malaysia. You're approachable, relatable, and can chat about anything - from campus life to pop culture to general life stuff.

        PERSONALITY TRAITS:
        - Conversational and casual, like talking to a friend
        - Can discuss ANY topic naturally - music, movies, life, relationships, hobbies, current events, etc.
        - Use varied language - don't repeat the same phrases
        - Sometimes use Malaysian slang appropriately (like "lah", "lor", but don't overdo it)
        - Show personality - be enthusiastic, empathetic, or humorous when appropriate
        - Ask follow-up questions to keep conversation flowing
        - Remember you're talking to students, so be relatable about all aspects of student life
        - Vary your response structure - sometimes paragraphs, sometimes lists, sometimes mixed
        - Be spontaneous and natural in your responses

        CONVERSATION APPROACH:
        - If it's MMU-related: Use your campus knowledge naturally
        - If it's general topics: Chat like a normal friend would - give opinions, share thoughts, be engaging
        - If it's pop culture: Be up-to-date and enthusiastic (music, movies, trends, etc.)
        - If it's personal/life advice: Be supportive and understanding
        - Always maintain a friendly, student-to-student vibe regardless of topic

        MMU CAMPUS KNOWLEDGE (use when relevant):
        Key Food Spots: MMU Starbees, He & She Cafe, Restoran Haji Tapah Bistro, Deen's Cafe, Bazaar Food Court
        Activities & Spaces: Siti Hasmah Digital Library, Sports Complex, Student lounges, Dewan Tun Canselor (DTC)
        Faculties: FOE (Engineering), FOM (Management), FCM (Creative Multimedia), FCI (Computing), Law, etc.

        RESPONSE STYLE GUIDELINES:
        - Mix up your openings: "Oh!", "Hmm,", "Ah,", "Hey there!", "I get it,", etc.
        - Use different structures based on the topic
        - Show genuine interest in whatever they're talking about
        - Be encouraging and supportive
        - Don't force MMU content into non-MMU conversations
        - Vary your emoji usage appropriately
        - Ask questions back to keep the conversation going
        - Be authentic - if you don't know something recent, just say so

        IMPORTANT: You can talk about ANYTHING, not just MMU stuff. Be a well-rounded conversational partner.

        Current time context: {datetime.now().strftime("%H:%M on %A")}
        Student message: "{user_message}"

        Respond as Queen Elizabeth III would - naturally, helpfully, and with personality. Keep it conversational and engaging."""
        
        # Generate AI response with error handling
        try:
            response = model.generate_content(context_prompt)
            
            if response.text:
                ai_response = response.text.strip()
                # Add some randomness to prevent identical responses
                ai_response = add_conversational_flair(ai_response, user_message)
            else:
                ai_response = get_natural_fallback_response(user_message)
                
        except Exception as ai_error:
            print(f"Gemini API error: {ai_error}")
            ai_response = get_natural_fallback_response(user_message)
        
        return jsonify({'response': ai_response})
        
    except Exception as e:
        print(f"Error in chat route: {e}")
        error_responses = [
            "Oops, something went a bit wonky on my end! Mind trying that again?",
            "Ah, technical difficulties! Give me another shot?",
            "Sorry, I seemed to have a brain freeze there. What were you saying?",
            "Hmm, that didn't work as expected. Try asking me again?"
        ]
        return jsonify({
            'response': random.choice(error_responses),
            'error': True
        }), 500

def handle_venue_query(message):
    """Handle venue/classroom location queries"""
    venue_patterns = [
        r'\b([CMNR]?[JLNQR][MABC][RX]\s*\d{4})\b',  # Standard venue codes
        r'where\s+is\s+([CMNR]?[JLNQR][MABC][RX]\s*\d{4})',
        r'find\s+([CMNR]?[JLNQR][MABC][RX]\s*\d{4})',
        r'location\s+of\s+([CMNR]?[JLNQR][MABC][RX]\s*\d{4})'
    ]
    
    message_upper = message.upper()
    
    for pattern in venue_patterns:
        match = re.search(pattern, message_upper)
        if match:
            venue_code = match.group(1).replace(' ', '')
            venue_info = parse_venue_code(venue_code)
            
            if venue_info:
                responses = [
                    f"Found it! {venue_code} is at {venue_info['full_location']}. Need directions on how to get there?",
                    f"Ah, {venue_code}! That's located at {venue_info['full_location']}. Hope you're not running late!",
                    f"Your class at {venue_code} is in {venue_info['full_location']}. Pro tip: give yourself some extra time to find it if it's your first time!",
                    f"Let me help you out - {venue_code} is at {venue_info['full_location']}. The campus can be confusing at first, but you'll get used to it!"
                ]
                return random.choice(responses)
            else:
                return f"Hmm, I couldn't parse that venue code '{venue_code}' properly. Could you double-check it? MMU codes usually follow a specific format."
    
    return None

def add_conversational_flair(response, original_message):
    """Add some randomness and personality to prevent repetitive responses"""
    
    # Add occasional casual interjections at the start
    casual_starters = ["Oh, ", "Ah, ", "Hey, ", "Hmm, ", "Well, ", "So, ", "Right, ", ""]
    
    # Don't modify if it already starts conversationally
    if not any(response.lower().startswith(word) for word in ['oh', 'ah', 'hey', 'hmm', 'well', 'so', 'right']):
        if random.random() < 0.3:  # 30% chance to add a casual starter
            response = random.choice(casual_starters) + response.lower()[0] + response[1:]
    
    # Add occasional follow-up questions
    follow_ups = [
        " What do you think?",
        " Does that help?", 
        " Let me know if you need more info!",
        " Anything else I can help with?",
        ""
    ]
    
    if random.random() < 0.4:  # 40% chance to add follow-up
        if not response.endswith(('?', '!', '.')):
            response += random.choice(follow_ups)
    
    return response

def get_natural_fallback_response(message):
    """More natural fallback responses based on message content"""
    message_lower = message.lower()
    current_hour = datetime.now().hour
    
    # Check if it's MMU-specific first
    mmu_keywords = ['mmu', 'multimedia university', 'campus', 'food street', 'starbees', 'library', 'study', 'class', 'exam']
    is_mmu_related = any(keyword in message_lower for keyword in mmu_keywords)
    
    if is_mmu_related:
        # Handle MMU-specific queries
        if any(word in message_lower for word in ['hungry', 'food', 'eat', 'lunch', 'dinner', 'breakfast', 'makan']):
            return get_natural_food_response(current_hour, message_lower)
        
        elif any(word in message_lower for word in ['bored', 'boring', 'nothing', 'free time', 'what to do', 'activities']):
            return get_natural_activity_response(current_hour, message_lower)
        
        elif any(word in message_lower for word in ['tired', 'sleepy', 'exhausted', 'rest', 'break']):
            rest_responses = [
                "Sounds like you need a breather! He & She Cafe in the library is pretty chill for a quiet break. Or if you want some fresh air, there are nice spots around campus to just sit and relax.",
                "Feeling drained? I totally get it. The student lounges are great for just vegging out, or grab a coffee from Starbees and find a quiet corner. Sometimes a change of scenery helps!",
                "Ah, the student struggle is real. If you need to recharge, the library has some comfy spots, or the prayer rooms are super peaceful. Don't forget to eat something too - low energy might just be hunger in disguise!"
            ]
            return random.choice(rest_responses)
        
        elif any(word in message_lower for word in ['study', 'exam', 'assignment', 'homework', 'library']):
            study_responses = [
                "Study time, huh? The library has different vibes on each floor - some are dead quiet, others are more social. He & She Cafe is perfect if you want to study with some background noise and good coffee.",
                "For serious study sessions, I'd recommend the quiet zones in the library. But if you're doing group work, the discussion rooms are clutch. Pro tip: book them in advance during exam season!",
                "Library's your best bet, but don't forget about the faculty study rooms too. Less crowded sometimes. And hey, take breaks - grab something from Food Street when your brain needs fuel!"
            ]
            return random.choice(study_responses)
    
    # For general/non-MMU topics, be conversational and engaging
    general_responses = [
        "Hey! I'm up for chatting about pretty much anything. What's on your mind?",
        "What's up? Whether it's about campus life, music, movies, or just random thoughts - I'm here for it!",
        "Hi there! Feel free to chat about whatever you want - I'm not just about MMU stuff, we can talk about anything that interests you!",
        "Hey! I'm all ears - whether you want to talk about campus, pop culture, life in general, or just need someone to chat with. What's going on?"
    ]
    return random.choice(general_responses)

def get_natural_food_response(current_hour, message_lower):
    """Natural food suggestions based on time and context"""
    
    if 6 <= current_hour <= 10:
        responses = [
            "Morning hunger hitting? Starbees has decent breakfast options and good coffee to wake you up. If you want something more local, the Main Cafeteria usually has some traditional breakfast stuff too.",
            "Breakfast time! I'd go for He & She Cafe if you want a quieter morning vibe - it's right in the library so you can ease into the day. Starbees is good too if you need that caffeine kick!",
            "Early bird, eh? For breakfast I'd say Starbees for the coffee and pastries, or check out what the Main Cafeteria has - they sometimes have local breakfast options that hit different in the morning."
        ]
    elif 11 <= current_hour <= 14:
        responses = [
            "Lunch time! If you're on a budget, Food Street is where it's at - cheap and filling. Haji Tapah is solid for some proper mamak food. What kind of mood are you in?",
            "Ah, the lunch rush! Food Street gets busy but it's worth it for the prices. If you want somewhere a bit more chill, Deen's Cafe is underrated. Or Haji Tapah if you're craving some roti canai!",
            "Lunchtime decisions! Food Street is the student go-to for a reason - variety and won't break the bank. But if you want to treat yourself a bit, He & She Cafe has some nice options too."
        ]
    elif 14 <= current_hour <= 20:
        responses = [
            "Afternoon munchies? He & She Cafe is perfect for a study break snack. If you want something more substantial, Food Street is always buzzing, or hit up Haji Tapah for some comfort food.",
            "Dinner time approaching! Haji Tapah is great for that mamak experience, or if you want more options, the Main Cafeteria has different stalls. What are you in the mood for?",
            "Evening food hunt! If you've been studying all day, treat yourself - maybe Deen's Cafe for something different, or stick with the reliable Food Street. Haji Tapah's also good for late dining."
        ]
    else:
        responses = [
            "Late night cravings? Most campus places close early, but there might be some 24-hour options in Cyberjaya nearby. Or stock up earlier next time - campus vending machines are your late-night friends!",
            "Night owl hunger! Campus options are limited this late, but some external places in Cyberjaya stay open. Pro tip: grab some snacks during the day for these moments!"
        ]
    
    return random.choice(responses)

def get_natural_activity_response(current_hour, message_lower):
    """Natural activity suggestions"""
    
    base_responses = [
        "Boredom striking? The sports complex is actually pretty cool - free gym access and courts if you want to get moving. Or if you're more of a chill person, library has social areas that aren't just for studying.",
        "Nothing to do? Time to explore! Campus has some nice walking spots, or check if there's anything happening at DTC. Student lounges are also good for just hanging out and meeting people.",
        "Feeling restless? Sports complex is solid if you want to be active, or just wander around campus - you might discover spots you didn't know existed. The library isn't just for books either!",
        "Bored, huh? Perfect time to check out what student clubs are up to, or just grab a coffee from He & She and people-watch in the library. Sometimes the best activities are the spontaneous ones!"
    ]
    
    return random.choice(base_responses)

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
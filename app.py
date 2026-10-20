from flask import Flask, request, jsonify
import requests
import google.generativeai as genai
import os

app = Flask(__name__)

# --- ENVIRONMENT CONFIGURATION (Read securely from Render) ---
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# This must match what you type into Meta Developers webhook setup
VERIFY_TOKEN = "my_secure_webhook_verify_token_123" 

# Configure Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- THE GARDENS JHAMSIKHEL PROFILE ---
RESTAURANT_KNOWLEDGE = """
You are the official AI assistant for "The Gardens", a beautiful restaurant and hub located in Jhamsikhel, Kathmandu, Nepal.
Your goal is to answer customer questions politely, accurately, and assist with bookings, menu items, and location details.

OUR RULES:
1. Keep answers conversational, warm, and helpful. Use emojis like 🌿, 🍹, 🍕, 🕒.
2. If customers ask in Nepali or a mix of English/Nepali (Roman Nepali), reply warmly in the same style or clear English.
3. Never make up details. If you don't know an answer, ask them to drop their phone number so the team can contact them directly.

OUR DETAILS:
- Location: Jhamsikhel, Lalitpur (Kathmandu Valley), Nepal. Right in the heart of the Jhamsikhel food/cafe hub. 
- Vibe: Beautiful garden space, outdoor seating, perfect for gatherings, dates, and live events.
- Opening Hours: Open daily from 11:00 AM to 10:00 PM.
- How to Book a Table: We accept reservations! For groups or special garden table requests, please provide your Name, Phone Number, Date, Time, and Number of Guests right here in this DM, or tell them to call the restaurant phone line directly.
- Menu Highlights:
  * Continental & Fusion: Wood-fired pizzas, gourmet burgers, pastas, and specialized main courses.
  * Local Flavors & Platters: Great selection of snacks, momos, and multi-cuisine platters perfect for sharing.
  * Bar & Coffee: Full bar serving signature cocktails, mocktails, chilled beers, and barista-crafted specialty coffee.
- Events: We frequently host live music, outdoor screening events, and acoustic nights. Ask them to follow our stories for this week's lineup!
"""

def get_ai_response(user_message):
    """Sends the user's message to Gemini with The Gardens context."""
    try:
        prompt = f"{RESTAURANT_KNOWLEDGE}\n\nCustomer asks: '{user_message}'\nYour helpful response:"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "🌿 Thanks for messaging The Gardens, Jhamsikhel! We are currently experiencing a high volume of messages. Please drop your contact number and query, and our team will get back to you shortly!"

def send_instagram_dm(recipient_id, message_text):
    """Sends a message back to the customer via the Meta Graph API."""
    # FIXED: Added 'graph.' domain, trailing slashes, and Meta Graph API version prefix
    url = f"https://graph.facebook.com/v20.0/{INSTAGRAM_ACCOUNT_ID}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    headers = {"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        res_data = response.json()
        print(f"Meta Graph API Response ({response.status_code}):", res_data)
        return res_data
    except Exception as e:
        print(f"Error calling Meta Graph API: {e}")
        return None

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. Meta Webhook URL Verification
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook successfully verified by Meta!")
            return challenge, 200
        print("Verification token mismatch!")
        return 'Verification token mismatch', 403

    # 2. Handling Real-Time DMs from Instagram
    if request.method == 'POST':
        data = request.json
        print("Incoming Webhook Data:", data)  # Useful for debugging incoming payloads in Render logs
        
        try:
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    # Ignore echoes or bot's own sent messages
                    if 'message' in messaging_event and 'text' in messaging_event['message']:
                        if messaging_event['message'].get('is_echo'):
                            continue
                            
                        user_message = messaging_event['message']['text']
                        print(f"User ({sender_id}) sent: {user_message}")
                        
                        # Generate the AI answer using The Gardens data
                        ai_reply = get_ai_response(user_message)
                        
                        # Send it back to the customer's Instagram inbox
                        send_instagram_dm(sender_id, ai_reply)
                        
        except Exception as e:
            print(f"Error processing Meta webhook payload: {e}")
            
        return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    # FIXED: Binds to Render's dynamic PORT environment variable and listens on 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

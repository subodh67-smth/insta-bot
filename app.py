from flask import Flask, request, jsonify
import requests
import google.generativeai as genai
import os

app = Flask(__name__)

# --- ENVIRONMENT CONFIGURATION (Read securely from Render) ---
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# This must match what you typed into Meta Developers webhook setup
VERIFY_TOKEN = "my_secure_webhook_verify_token_123"

# --- THE GARDENS JHAMSIKHEL PROFILE & SYSTEM INSTRUCTIONS ---
RESTAURANT_KNOWLEDGE = """
You are the official AI assistant for "The Gardens", a premier restaurant and hub in Jhamsikhel, Lalitpur (Kathmandu Valley), Nepal.

CRITICAL INSTRUCTIONS:
1. ALWAYS read the customer's specific question and answer THAT topic directly.
2. IF ASKED ABOUT MENU / FOOD / DRINKS: List our menu highlights immediately using emojis (Wood-fired Pizzas 🍕, Gourmet Burgers 🍔, Pastas 🍝, Momos 🥟, Barista Coffee ☕, Signature Cocktails 🍹, Chilled Beers 🍺). Do NOT talk about location unless specifically asked.
3. IF ASKED ABOUT LOCATION / DIRECTIONS: State that we are located in Jhamsikhel, Lalitpur (Kathmandu Valley), right in the heart of the cafe hub.
4. IF ASKED ABOUT BOOKINGS / TABLES: Ask for Name, Phone Number, Date, Time, and Number of Guests right here in DM.
5. Keep answers warm, helpful, conversational, and concise.
"""

# Configure Gemini AI safely
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_ai_response(user_message):
    """Generates a direct response from Gemini using gemini-3.8-flash."""
    prompt = f"{RESTAURANT_KNOWLEDGE}\n\nCustomer asks: '{user_message}'\nYour direct response:"
    
    try:
        # Using the correct gemini-3.8-flash model endpoint
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"!!! GEMINI API ERROR: {e}")
        return "🌿 Thanks for messaging The Gardens, Jhamsikhel! How can we assist you today? Please drop your query or phone number, and our team will get back to you shortly!"

def send_instagram_dm(recipient_id, message_text):
    """Sends a message back to the customer via the Meta Graph API."""
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

@app.route('/privacy')
def privacy_policy():
    """Privacy policy route required for Meta App verification."""
    return """
    <h1>Privacy Policy for The Gardens Jhamsikhel Chatbot</h1>
    <p>This Instagram Chatbot processes customer direct messages to deliver automated restaurant information and assistance.</p>
    <p>We do not store or share personal user data with external third parties.</p>
    """, 200

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
        data = request.get_json(force=True, silent=True) or {}
        print("Incoming Raw Webhook Payload:", data)
        
        try:
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event.get('sender', {}).get('id')
                    
                    # Ignore messages sent by your own Instagram Business Account ID to block loops
                    if sender_id == INSTAGRAM_ACCOUNT_ID:
                        print("Ignoring outgoing echo message from our own bot account.")
                        continue
                    
                    if 'message' in messaging_event and 'text' in messaging_event['message']:
                        msg_data = messaging_event['message']
                        
                        if msg_data.get('is_echo'):
                            continue
                            
                        user_message = msg_data['text']
                        print(f"Valid Customer ({sender_id}) asked: '{user_message}'")
                        
                        # Generate the AI answer using Gemini
                        ai_reply = get_ai_response(user_message)
                        
                        # Send reply back to customer's Instagram DM inbox
                        send_instagram_dm(sender_id, ai_reply)
                        
        except Exception as e:
            print(f"Error processing Meta webhook payload: {e}")
            
        return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

"""
SupportMate AI – Customer Support Chatbot
Flask backend using Gemini API with SSE streaming.
Falls back to intelligent demo responses if API quota is exceeded.
"""
import os
import json
import logging
import random
import time
import requests
from typing import List, Dict

from flask import Flask, render_template, request, Response, jsonify, stream_with_context
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()  # MUST be called before any os.getenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
FORCE_DEMO = os.getenv("FORCE_DEMO", "0").strip() == "1"

if FORCE_DEMO or (not GEMINI_API_KEY and not OPENAI_API_KEY):
    API_KEY = None
    BASE_URL = ""
    MODEL = "demo"
elif GEMINI_API_KEY:
    API_KEY = GEMINI_API_KEY
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gemini-2.0-flash-lite"
else:
    API_KEY = OPENAI_API_KEY
    BASE_URL = "https://api.openai.com/v1/"
    MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-3.5-turbo"

TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "600"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "10"))
FLASK_ENV = os.getenv("FLASK_ENV", "production")
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "127.0.0.1")

SYSTEM_PROMPT = """You are SupportMate AI, a friendly and professional customer support assistant.
Your goal is to help customers with their questions, issues, billing inquiries, product information, and general support needs.

Guidelines:
- Always be polite, empathetic, and helpful
- Provide clear and concise answers
- If you don't know something, say so honestly and suggest alternatives
- For technical issues, provide step-by-step troubleshooting guidance
- For billing issues, be understanding and offer to escalate if needed
- Keep responses focused and easy to understand
- End responses with a follow-up question or offer for further help"""

# ---------------------------------------------------------------------------
# Demo Responses (used when API quota is exceeded or key is missing)
# ---------------------------------------------------------------------------
DEMO_RESPONSES = {
    "order": [
        "I'd be happy to help you track your order! 📦\n\nTo locate your order, please provide your **Order ID** (found in your confirmation email). Once I have that, I can give you real-time tracking details.\n\nYou can also track orders directly at our website under **My Orders > Order History**.\n\nIs there anything else I can help you with?",
        "Great question about your order! Here's how to check your order status:\n\n1. **Log in** to your account\n2. Go to **My Orders** in the top menu\n3. Click on your order to see the status\n\nIf you don't have an account, check your **confirmation email** for a tracking link. Would you like more help?",
    ],
    "billing": [
        "I understand billing concerns can be stressful — I'm here to help! 💳\n\nHere's what I can assist with:\n- **View your invoices** under Account > Billing History\n- **Update payment methods** in Account > Payment Settings\n- **Dispute a charge** by clicking 'Report an Issue' next to any transaction\n\nFor complex billing issues, I can escalate to our billing team who respond within 24 hours. Would you like me to do that?",
        "No worries, billing issues are easy to resolve! Let me help.\n\nCould you tell me more about the issue?\n- **Unexpected charge?** I can review your recent transactions\n- **Failed payment?** I can help update your payment details\n- **Request a refund?** I can initiate the process for you\n\nWhat's the specific billing concern?",
    ],
    "password": [
        "Resetting your password is quick and easy! 🔐\n\n**Steps to reset:**\n1. Go to the **Login page**\n2. Click **'Forgot Password?'**\n3. Enter your registered email address\n4. Check your inbox for a reset link (valid for 30 minutes)\n5. Click the link and create a new password\n\n**Tips for a strong password:**\n- At least 8 characters\n- Mix of uppercase, lowercase, numbers, and symbols\n\nDid the reset email arrive? Let me know if you need further help!",
    ],
    "return": [
        "I'm sorry the product didn't meet your expectations! Let me help with your return. ↩️\n\n**Our Return Policy:**\n- Returns accepted within **30 days** of purchase\n- Item must be in **original condition**\n- Refunds processed within **5-7 business days**\n\n**To start a return:**\n1. Go to **My Orders** and select the item\n2. Click **'Return or Exchange'**\n3. Select your reason and preferred resolution\n4. Print the prepaid return label\n\nWould you like me to initiate the return for you?",
    ],
    "default": [
        "Thank you for reaching out to SupportMate AI! 👋\n\nI'm here to help you with:\n- 📦 **Order tracking** and delivery issues\n- 💳 **Billing** and payment questions\n- 🔐 **Account** and password help\n- ↩️ **Returns** and refunds\n- 🛠️ **Technical support**\n\nCould you tell me more about what you need help with today? I'll do my best to resolve it quickly!",
        "Hello! Welcome to SupportMate AI. 😊\n\nI'd love to help you today! Could you describe your issue in a bit more detail so I can provide the most accurate assistance?\n\nWhether it's an order, billing, account, or anything else — I've got you covered!",
        "I appreciate you contacting our support team! I'm SupportMate AI, and I'm ready to assist.\n\nTo best help you, could you clarify:\n1. What product or service is this about?\n2. What issue are you experiencing?\n3. When did this start?\n\nWith these details, I can provide a fast and accurate solution!",
        "Great question! Let me look into that for you. 🔍\n\nBased on what you've described, here are a few things to try:\n\n1. **Refresh the page** and try again\n2. **Clear your browser cache** (Ctrl+Shift+Delete)\n3. **Try a different browser** or device\n\nIf the issue persists, please send us a screenshot and I'll escalate this to our technical team immediately. Is there anything else I can help with?",
        "I completely understand your concern, and I want to make sure this is resolved for you! 🙌\n\nHere's what I'll do:\n- Document your issue for our team\n- Provide you with a **case number** for tracking\n- Ensure our specialist contacts you within **2 business hours**\n\nIn the meantime, is there anything else I can help clarify?",
    ],
}


def get_demo_response(user_message: str) -> str:
    """Return a keyword-matched demo response."""
    msg_lower = user_message.lower()
    if any(w in msg_lower for w in ["order", "track", "delivery", "ship", "package"]):
        return random.choice(DEMO_RESPONSES["order"])
    elif any(w in msg_lower for w in ["bill", "invoice", "charge", "payment", "refund", "money", "cost", "price"]):
        return random.choice(DEMO_RESPONSES["billing"])
    elif any(w in msg_lower for w in ["password", "login", "sign in", "account", "forgot", "reset"]):
        return random.choice(DEMO_RESPONSES["password"])
    elif any(w in msg_lower for w in ["return", "exchange", "send back", "broken", "damaged"]):
        return random.choice(DEMO_RESPONSES["return"])
    else:
        return random.choice(DEMO_RESPONSES["default"])


def stream_demo(text: str):
    """Yield demo response as SSE tokens word by word for a realistic effect."""
    words = text.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        yield f"data: {json.dumps({'token': token})}\n\n"
        time.sleep(0.04)  # ~25 words/sec streaming feel
    yield f"data: {json.dumps({'done': True})}\n\n"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("supportmate_ai")

for _var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_var, None)

if not API_KEY:
    logger.warning("No API key found — running in Demo Mode")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sanitize_messages(raw: List[Dict]) -> List[Dict]:
    """Clean and validate chat history from the client."""
    if not isinstance(raw, list):
        raise ValueError("history must be a list")
    cleaned = []
    for msg in raw[-MAX_HISTORY:]:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        cleaned.append({"role": role, "content": content.strip()[:4000]})
    return cleaned


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": MODEL if API_KEY else "demo",
        "api_key_configured": bool(API_KEY),
        "demo_mode": not bool(API_KEY),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON body."}), 400

    user_message = (body.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Message is required."}), 400
    if len(user_message) > 4000:
        return jsonify({"error": "Message too long (max 4000 chars)."}), 400

    try:
        history = sanitize_messages(body.get("history", []))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # ── Demo mode: no API key configured ─────────────────────────────────────
    if not API_KEY:
        logger.info("Demo mode — responding to: %s", user_message[:60])
        return Response(
            stream_with_context(stream_demo(get_demo_response(user_message))),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Live AI mode ──────────────────────────────────────────────────────────
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            url = BASE_URL.rstrip("/") + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            }
            payload = {
                "model": MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
                "stream": True,
            }
            with requests.post(
                url, headers=headers, json=payload, stream=True, timeout=60
            ) as resp:
                # If the API key is invalid (400) or quota exceeded (429), switch to demo mode
                if resp.status_code in (400, 429):
                    logger.warning("API key invalid or quota exceeded — switching to demo mode for this request")
                    yield from stream_demo(get_demo_response(user_message))
                    return

                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        if data_str == "[DONE]":
                            yield f"data: {json.dumps({'done': True})}\n\n"
                        continue
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        finish = chunk.get("choices", [{}])[0].get("finish_reason")
                        if finish:
                            yield f"data: {json.dumps({'done': True})}\n\n"
                    except Exception:
                        continue

        except Exception as exc:
            logger.exception("Streaming error")
            # Fallback to demo on any error
            yield from stream_demo(get_demo_response(user_message))

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "Request body too large"}), 413


@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    debug = FLASK_ENV.lower() == "development"
    mode = "Live AI" if API_KEY else "Demo"
    logger.info("Starting SupportMate AI [%s Mode] on %s:%s", mode, HOST, PORT)
    app.run(host=HOST, port=PORT, debug=debug, threaded=True)

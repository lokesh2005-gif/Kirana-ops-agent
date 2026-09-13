import os
import logging
import asyncio
import collections
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///kirana.db"

from app.agent.agent import get_chat_session
from app.db.database import engine
from app.db.models import Base
from app.db.seed import seed_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory State
chat_sessions = {}
processed_updates = collections.deque(maxlen=1000)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Kirana Ops Agent! Send me items to bill, check stock, or manage Khata.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I can help with billing, inventory, khata, and analytics.")

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
    await update.message.reply_text("Conversation cleared! Standing preferences and store data remain untouched.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_id = update.update_id
    
    # Deduplication check
    if update_id in processed_updates:
        logger.info(f"Duplicate update {update_id} received, ignoring.")
        return
    processed_updates.append(update_id)

    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = get_chat_session()
    
    chat = chat_sessions[chat_id]
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        
        # Gemini interaction with retry logic for free tier rate limits
        max_retries = 3
        response_text = ""
        loop = asyncio.get_event_loop()
        
        for attempt in range(max_retries):
            try:
                response = await loop.run_in_executor(None, chat.send_message, user_text)
                response_text = response.text
                break
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.warning("Rate limit hit, waiting before retry...")
                    await asyncio.sleep(25)
                else:
                    raise e
        
        # Document handling — agent tools prefix file paths with PDF_FILE: or PPTX_FILE:
        import re as _re
        file_matches = _re.findall(r'(?:PDF_FILE|PPTX_FILE):([\w/\\.:\-\s]+\.(?:pdf|pptx))', response_text)
        
        for fp in file_matches:
            fp = fp.strip()
            if os.path.exists(fp):
                with open(fp, 'rb') as doc:
                    await update.message.reply_document(document=doc)
            # Strip the raw file path marker from visible response text
            response_text = response_text.replace(f"PDF_FILE:{fp}", "").replace(f"PPTX_FILE:{fp}", "").strip()
        
        if response_text:
            await update.message.reply_text(response_text)
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(f"Error processing your request: {str(e)}")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN missing in environment.")

    # Provision database
    Base.metadata.create_all(bind=engine)
    seed_db()

    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
    port = int(os.environ.get("PORT", "8443"))

    if use_webhook:
        webhook_url = os.environ.get("WEBHOOK_URL", "").strip().strip("\"'<> ")
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip().strip("\"'<> ")

        # If webhook_url is empty or contains placeholder text, fallback to RENDER_EXTERNAL_URL
        placeholders = ["<", ">", "your-app", "your-service", "example.com"]
        is_placeholder = any(p in webhook_url.lower() for p in placeholders)

        if (not webhook_url or is_placeholder) and render_url:
            logger.info(f"Using RENDER_EXTERNAL_URL fallback: {render_url}")
            webhook_url = f"{render_url.rstrip('/')}/webhook"

        if not webhook_url or any(p in webhook_url.lower() for p in placeholders):
            logger.warning("No valid webhook URL found. Falling back to Polling mode with HTTP health server for Render.")
            use_webhook = False

    if use_webhook:
        # Ensure HTTPS protocol
        if webhook_url.startswith("http://"):
            webhook_url = "https://" + webhook_url[len("http://"):]
        elif not webhook_url.startswith("https://"):
            webhook_url = f"https://{webhook_url}"

        # Parse and sanitize URL
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(webhook_url)
        path = parsed.path.strip("/")
        secret_path = path if path else "webhook"

        # Remove non-standard ports from public URL (Telegram only supports 443, 80, 88, 8443)
        # Render terminates TLS on port 443 externally and routes to internal PORT
        netloc = parsed.netloc.split(":")[0]
        sanitized_url = urlunparse(("https", netloc, f"/{secret_path}", "", "", ""))

        logger.info(f"Starting webhook on internal port {port}, url_path=/{secret_path}, public_url={sanitized_url}")
        try:
            app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=secret_path,
                webhook_url=sanitized_url,
            )
            return
        except Exception as e:
            logger.error(f"Webhook startup failed ({e}). Falling back to Polling mode.")
            use_webhook = False

    # Polling mode with lightweight HTTP health check server for Render / cloud platforms
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"kirana-ops-agent"}')

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass  # suppress noisy health check logs

    try:
        health_server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        t = threading.Thread(target=health_server.serve_forever, daemon=True)
        t.start()
        logger.info(f"HTTP health server started on port {port} (satisfies Render web service check)")
    except Exception as e:
        logger.warning(f"Could not bind health server on port {port}: {e}")

    logger.info("Starting Telegram bot in Polling mode...")
    app.run_polling()

if __name__ == "__main__":
    main()

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
        
        # Document handling for PDF/PPTX from artifacts folder
        file_paths = re.findall(r'(?:[A-Za-z]:)?(?:[\\/]?[\w\-\s.]+)*artifacts[\\/][\w\-\s]+\.(?:pdf|pptx)', response_text)
        if not file_paths:
            file_paths = re.findall(r'artifacts/[a-zA-Z0-9_\-\.]+\.(?:pdf|pptx)', response_text)

        for fp in file_paths:
            fp = fp.strip()
            if os.path.exists(fp):
                with open(fp, 'rb') as doc:
                    await update.message.reply_document(document=doc)
        
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
    if use_webhook:
        port = int(os.environ.get("PORT", "8443"))
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        logger.info(f"Starting webhook on port {port}")
        app.run_webhook(listen="0.0.0.0", port=port, webhook_url=webhook_url)
    else:
        logger.info("Starting polling mode for local dev...")
        app.run_polling()

if __name__ == "__main__":
    main()

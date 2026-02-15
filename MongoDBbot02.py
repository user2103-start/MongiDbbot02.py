import logging
import asyncio
import uuid
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- RENDER WEB SERVER (FIXES PORT ERROR) ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is Alive and Running!"

def run_web():
    flask_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- CONFIGURATION ---
# Note: Use your actual credentials here
API_ID = 38456866
API_HASH = "30a8f347f538733a1d57dae8cc458ddc"
BOT_TOKEN = "8091813423:AAHoh4lnsf41ES3ECq7HdDy3DCmldWJUL5w"
ADMIN_ID = 6593129349
MAIN_CHANNEL_ID = -1003615939406
BACKUP_CHANNEL_ID = -1003655362946
MAIN_CH_LINK = "https://t.me/+KqXHQsAmndE3MmM1"
BACKUP_CH_LINK = "https://t.me/+DWoy0pgaw9VjOGM1"

# --- MONGODB SETUP ---
MONGO_URI = "mongodb+srv://Mashupmaster:88eJt75forhI6YXw@cluster0.61rdehu.mongodb.net/?appName=Cluster0" 
client = MongoClient(MONGO_URI)
db = client['file_storage_bot_v3']
files_col = db['files']
users_col = db['users']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- HELPERS ---
async def is_member(user_id, context):
    """Check force join"""
    for ch_id in [MAIN_CHANNEL_ID, BACKUP_CHANNEL_ID]:
        try:
            member = await context.bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']: return False
        except: return False
    return True

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Save user for broadcast
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})

    args = context.args
    
    # Force Join Check (Except Admin)
    if user_id != ADMIN_ID and not await is_member(user_id, context):
        file_key = args[0] if args else "none"
        keyboard = [
            [InlineKeyboardButton("Main Channel 📢", url=MAIN_CH_LINK)],
            [InlineKeyboardButton("Backup Channel 🛡️", url=BACKUP_CH_LINK)],
            [InlineKeyboardButton("Verify Me ✅", callback_data=f"verify_{file_key}")]
        ]
        return await update.message.reply_text(
            f"Oye {update.effective_user.first_name}! 🤗\nBot use karne ke liye channels join karo.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    if args:
        return await send_file(update, context, args[0])
    
    welcome_text = "Swagat hai Maalik! 🔥" if user_id == ADMIN_ID else "Dost, file chahiye toh link use karo!"
    await update.message.reply_text(welcome_text)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sends media -> Link generates"""
    if update.effective_user.id != ADMIN_ID: return

    media = update.message.effective_attachment
    if isinstance(media, list): media = media[-1] # For photos
    
    if not media: return

    file_id = media.file_id
    # Permanent unique ID using UUID
    unique_id = str(uuid.uuid4())[:10]
    
    files_col.insert_one({"file_key": unique_id, "file_id": file_id})
    
    bot_info = await context.bot.get_me()
    share_link = f"https://t.me/{bot_info.username}?start={unique_id}"
    await update.message.reply_text(f"🚀 **Permanent Link Ban Gaya:**\n\n`{share_link}`")

async def send_file(update, context, file_key):
    chat_id = update.effective_chat.id
    data = files_col.find_one({"file_key": file_key})

    if data:
        # NO AUTO-DELETE HERE ✅
        await context.bot.send_document(
            chat_id=chat_id, 
            document=data['file_id'], 
            caption="📦 **Aapki File!**\n\nEnjoy karein!"
        )
    else:
        await context.bot.send_message(chat_id=chat_id, text="❌ Invalid Link!")

# --- ADMIN FEATURES ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    u_count = users_col.count_documents({})
    f_count = files_col.count_documents({})
    await update.message.reply_text(f"📊 **Stats:**\n\nUsers: {u_count}\nFiles: {f_count}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not update.message.reply_to_message:
        return await update.message.reply_text("Kissi message ko reply karke `/broadcast` likho.")
    
    users = users_col.find({})
    count = 0
    for user in users:
        try:
            await context.bot.copy_message(user['user_id'], update.effective_chat.id, update.message.reply_to_message.message_id)
            count += 1
        except: pass
    await update.message.reply_text(f"📢 Broadcast Complete! {count} users ko message mila.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')[1]
    if await is_member(query.from_user.id, context):
        await query.message.delete()
        if data != "none": await send_file(query, context, data)
        else: await query.message.reply_text("Verified! ✅")
    else:
        await query.answer("Join karlo pehle! 😤", show_alert=True)

# --- MAIN ---
def main():
    keep_alive() # Start Flask
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^verify_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_document))
    
    logger.info("Bot is Starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

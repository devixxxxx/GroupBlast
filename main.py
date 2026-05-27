import os
import json
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import threading

# ---------- CONFIG ----------
ADMIN_BOT_TOKEN = os.environ.get("ADMIN_BOT_TOKEN")
USER_BOT_TOKEN = os.environ.get("USER_BOT_TOKEN")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")

print(f"ADMIN_BOT_TOKEN: {ADMIN_BOT_TOKEN[:15] if ADMIN_BOT_TOKEN else 'NOT SET'}...")
print(f"USER_BOT_TOKEN: {USER_BOT_TOKEN[:15] if USER_BOT_TOKEN else 'NOT SET'}...")
print(f"ADMIN_USER_ID: {ADMIN_USER_ID}")

if not ADMIN_BOT_TOKEN or not USER_BOT_TOKEN or not ADMIN_USER_ID:
    print("ERROR: Environment variables not set properly!")
    exit(1)

USERS_FILE = "users.json"
SESSIONS_FILE = "sessions.json"

app = Flask(__name__)

# ---------- JSON Functions ----------
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def load_sessions():
    try:
        with open(SESSIONS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_sessions(sessions):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=4)

# ============= ADMIN BOT =============
print("Creating admin bot...")
admin_app = Application.builder().token(ADMIN_BOT_TOKEN).build()

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_USER_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("📜 List Users", callback_data="list_users")],
        [InlineKeyboardButton("❌ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📊 Active Sessions", callback_data="view_sessions")],
    ]
    await update.message.reply_text("🔐 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    users = load_users()
    
    if data == "add_user":
        await query.message.reply_text("Send user ID to add:\nExample: 123456789")
        context.user_data['admin_action'] = 'add_user'
        
    elif data == "list_users":
        if not users:
            await query.message.reply_text("No users found.")
        else:
            msg = "Registered Users:\n\n"
            for uid, info in users.items():
                msg += f"ID: {uid}\nAdded: {info['added_on']}\n\n"
            await query.message.reply_text(msg[:4000])
            
    elif data == "remove_user":
        if not users:
            await query.message.reply_text("No users to remove.")
        else:
            keyboard = [[InlineKeyboardButton(f"Remove {uid}", callback_data=f"remove_{uid}")] for uid in users.keys()]
            await query.message.reply_text("Select user to remove:", reply_markup=InlineKeyboardMarkup(keyboard))
            
    elif data == "view_sessions":
        sessions = load_sessions()
        if not sessions:
            await query.message.reply_text("No active sessions.")
        else:
            msg = "Active Sessions:\n\n"
            for tg_id, unique_id in sessions.items():
                msg += f"User: {tg_id} -> Logged in as: {unique_id}\n"
            await query.message.reply_text(msg[:4000])
            
    elif data.startswith("remove_"):
        user_to_remove = data.replace("remove_", "")
        users = load_users()
        if user_to_remove in users:
            del users[user_to_remove]
            save_users(users)
            await query.message.reply_text(f"User {user_to_remove} removed!")

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('admin_action') == 'add_user':
        user_id = update.message.text.strip()
        users = load_users()
        
        if user_id in users:
            await update.message.reply_text("User already exists!")
        else:
            users[user_id] = {"user_id": user_id, "added_on": str(datetime.now())}
            save_users(users)
            await update.message.reply_text(f"User {user_id} added!")
        
        context.user_data['admin_action'] = None

admin_app.add_handler(CommandHandler("start", admin_start))
admin_app.add_handler(CallbackQueryHandler(admin_callback))
admin_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message))

# ============= USER BOT =============
print("Creating user bot...")
user_app = Application.builder().token(USER_BOT_TOKEN).build()

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Auto Message System\n\n"
        "Commands (bina slash):\n"
        "login YOUR_ID - Login\n"
        "logout - Logout\n"
        "broadcast GROUP_ID1,GROUP_ID2 Your message - Send to groups\n"
        "myid - Check status\n\n"
        "Example:\n"
        "broadcast -100123456789,-100987654321 Hello!"
    )

async def user_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg_id = str(update.effective_user.id)
    
    try:
        unique_id = context.args[0]
    except:
        await update.message.reply_text("Usage: login YOUR_ID")
        return
    
    users = load_users()
    
    if unique_id in users:
        sessions = load_sessions()
        sessions[user_tg_id] = unique_id
        save_sessions(sessions)
        await update.message.reply_text(f"✅ Login successful! Welcome {unique_id}")
    else:
        await update.message.reply_text("❌ Invalid ID! Contact admin.")

async def user_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg_id = str(update.effective_user.id)
    sessions = load_sessions()
    
    if user_tg_id in sessions:
        del sessions[user_tg_id]
        save_sessions(sessions)
        await update.message.reply_text("✅ Logged out!")

async def user_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg_id = str(update.effective_user.id)
    sessions = load_sessions()
    
    if user_tg_id in sessions:
        await update.message.reply_text(f"Logged in as: {sessions[user_tg_id]}")
    else:
        await update.message.reply_text("Not logged in. Use login")

async def user_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg_id = str(update.effective_user.id)
    sessions = load_sessions()
    
    if user_tg_id not in sessions:
        await update.message.reply_text("Please login first!")
        return
    
    try:
        text = update.message.text
        parts = text.split(" ", 2)
        
        if len(parts) < 3:
            await update.message.reply_text("Usage: broadcast GROUP_ID1,GROUP_ID2 Your message")
            return
        
        group_part = parts[1]
        message = parts[2]
        group_ids = [g.strip() for g in group_part.split(",")]
        
        success = 0
        fail = 0
        
        for gid in group_ids:
            try:
                await context.bot.send_message(
                    chat_id=gid,
                    text=f"📢 Message from {sessions[user_tg_id]}:\n\n{message}"
                )
                success += 1
            except Exception as e:
                fail += 1
                print(f"Failed to send to {gid}: {e}")
        
        await update.message.reply_text(f"✅ Sent: {success} | ❌ Failed: {fail}")
        
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:100]}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    
    if text.startswith("login "):
        parts = text.split()
        if len(parts) >= 2:
            context.args = [parts[1]]
            await user_login(update, context)
        else:
            await update.message.reply_text("Usage: login YOUR_ID")
    
    elif text == "logout":
        await user_logout(update, context)
    
    elif text == "myid":
        await user_myid(update, context)
    
    elif text.startswith("broadcast "):
        update.message.text = text
        await user_broadcast(update, context)

user_app.add_handler(CommandHandler("start", user_start))
user_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# ============= FLASK =============
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ============= MAIN =============
if __name__ == "__main__":
    # Start Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    print("✅ Both bots are starting...")
    
    # Run admin bot
    print("Starting admin bot...")
    admin_app.run_polling()

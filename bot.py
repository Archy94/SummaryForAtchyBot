import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import openai

TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
openai.api_key = OPENAI_API_KEY

conn = sqlite3.connect("chat_messages.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        text TEXT,
        chat_id INTEGER,
        timestamp DATETIME
    )
""")
conn.commit()

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        user = update.message.from_user.full_name
        text = update.message.text
        chat_id = update.message.chat_id
        timestamp = datetime.now()

        c.execute("INSERT INTO messages (user, text, chat_id, timestamp) VALUES (?, ?, ?, ?)",
                  (user, text, chat_id, timestamp))
        conn.commit()

async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    since = datetime.now() - timedelta(hours=12)

    c.execute("SELECT user, text FROM messages WHERE chat_id=? AND timestamp > ?", (chat_id, since))
    rows = c.fetchall()

    if not rows:
        await context.bot.send_message(chat_id=chat_id, text="💤 В чате пока ничего интересного.")
        return

    conversation = "\n".join([f"{user}: {text}" for user, text in rows])
    prompt = f"Summarize this group chat in a concise and informal way:\n\n{conversation}"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a witty summarizer of Telegram group chats."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300
        )
        summary = response.choices[0].message.content.strip()
        await context.bot.send_message(chat_id=chat_id, text=f"🧠 Summary:\n{summary}")
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Ошибка при генерации саммари.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), store_message))
    app.add_handler(CommandHandler("summary", send_summary))

    app.run_polling()

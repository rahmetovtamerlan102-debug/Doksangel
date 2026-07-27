import os
import re
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Конфиг ---
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

# Flask для keepalive
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

# --- Функции проверки ---
def clean_phone(phone):
    return re.sub(r'\D', '', phone)

def get_phone_info(phone):
    report = {"phone": phone, "info": {}, "whatsapp": "Неизвестно", "leaks": []}
    clean = clean_phone(phone)
    
    # 1. htmlweb.ru
    try:
        r = requests.get(f"https://htmlweb.ru/phone/{phone}", timeout=5)
        if r.status_code == 200:
            text = r.text
            for key in ['Страна', 'Регион', 'Город', 'Оператор']:
                m = re.search(f'{key}[:\s]+([^<]+)', text)
                if m:
                    report["info"][key] = m.group(1).strip()
    except:
        pass
    
    # 2. WhatsApp
    try:
        r = requests.get(f"https://wa.me/{clean}", timeout=3, allow_redirects=True)
        report["whatsapp"] = "Зарегистрирован" if "WhatsApp" in r.text else "Не зарегистрирован"
    except:
        pass
    
    # 3. Leakcheck
    try:
        r = requests.get(f"https://leakcheck.io/search?q={clean}", timeout=5)
        if r.status_code == 200:
            bases = re.findall(r'<td>(.*?)</td>\s*<td>(.*?)</td>', r.text)
            report["leaks"] = [{"База": b[0].strip(), "Дата": b[1].strip()} for b in bases[:5]]
    except:
        pass
    
    return report

# --- Обработчики команд (синхронные) ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Привет! Отправь номер в формате +79123456789 — я покажу, что известно."
    )

def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not re.match(r'^\+?\d{10,15}$', text):
        update.message.reply_text("❌ Отправь номер в формате +79123456789")
        return
    
    update.message.reply_text("🔍 Ищу информацию...")
    report = get_phone_info(text)
    
    answer = f"📱 *Номер:* `{report['phone']}`\n"
    if report["info"]:
        for k, v in report["info"].items():
            answer += f"• *{k}:* {v}\n"
    answer += f"• *WhatsApp:* {report['whatsapp']}\n"
    if report["leaks"]:
        answer += "🔓 *Утечки:*\n"
        for leak in report["leaks"][:3]:
            answer += f"  - {leak['База']} ({leak['Дата']})\n"
    else:
        answer += "✅ Утечек не найдено"
    
    update.message.reply_text(answer, parse_mode="Markdown")

def error(update, context):
    print(f"Update {update} caused error {context.error}")

# --- Запуск Flask и бота ---
def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    import threading
    # Запускаем Flask в потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Создаём бота
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_error_handler(error)
    
    # Запускаем polling
    updater.start_polling()
    updater.idle()

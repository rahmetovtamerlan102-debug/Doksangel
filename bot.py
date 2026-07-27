import os
import re
import requests
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")  # Токен из переменных окружения
PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- Flask для keepalive ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# --- Функции проверки номера ---
def clean_phone(phone):
    return re.sub(r'\D', '', phone)

def get_phone_info(phone):
    report = {"phone": phone, "info": {}, "whatsapp": "Неизвестно", "leaks": []}
    clean = clean_phone(phone)
    
    # 1. htmlweb.ru (парсим)
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
    
    # 3. Leakcheck (первые 5)
    try:
        r = requests.get(f"https://leakcheck.io/search?q={clean}", timeout=5)
        if r.status_code == 200:
            bases = re.findall(r'<td>(.*?)</td>\s*<td>(.*?)</td>', r.text)
            report["leaks"] = [{"База": b[0].strip(), "Дата": b[1].strip()} for b in bases[:5]]
    except:
        pass
    
    return report

# --- Обработчики ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("👋 Привет! Отправь номер в формате +79123456789 — я покажу, что известно.")

@dp.message_handler(content_types=['text'])
async def handle_phone(message: types.Message):
    text = message.text.strip()
    if not re.match(r'^\+?\d{10,15}$', text):
        await message.reply("❌ Отправь номер в формате +79123456789")
        return
    
    await message.reply("🔍 Ищу...")
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
    
    await message.reply(answer, parse_mode="Markdown")

# --- Запуск ---
if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке (чтобы Render не убил процесс)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Запускаем polling бота
    executor.start_polling(dp, skip_updates=True)

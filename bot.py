import os
import re
import requests
import time
import threading
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

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
                m = re.search(rf'{key}:\s+([^<]+)', text)
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

def send_message(chat_id, text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def handle_update(update):
    if "message" not in update:
        return
    message = update["message"]
    chat_id = message["chat"]["id"]
    if "text" not in message:
        return
    text = message["text"].strip()
    
    if text == "/start":
        send_message(chat_id, "👋 Привет! Отправь номер в формате +79123456789 — я покажу, что известно.")
        return
    
    if not re.match(r'^\+?\d{10,15}$', text):
        send_message(chat_id, "❌ Отправь номер в формате +79123456789")
        return
    
    send_message(chat_id, "🔍 Ищу информацию...")
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
    
    send_message(chat_id, answer, parse_mode="Markdown")

def bot_polling():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            r = requests.get(url, params=params, timeout=35)
            if r.status_code == 200:
                data = r.json()
                if data["ok"]:
                    for update in data["result"]:
                        handle_update(update)
                        offset = update["update_id"] + 1
        except Exception as e:
            print("Polling error:", e)
        time.sleep(1)

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке (для keepalive)
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем основной цикл опроса
    bot_polling()

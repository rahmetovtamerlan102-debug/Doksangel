import os
import re
import requests
import time
import threading
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

# ---------- ОЧИСТКА НОМЕРА ----------
def clean_phone(phone):
    return re.sub(r'\D', '', phone)

# ---------- ПРОВЕРКИ ----------
def check_whatsapp(phone):
    clean = clean_phone(phone)
    try:
        r = requests.get(f"https://wa.me/{clean}", timeout=3, allow_redirects=True)
        return "✅ Зарегистрирован" if "WhatsApp" in r.text else "❌ Не найден"
    except:
        return "⚠️ Ошибка проверки"

def check_telegram(phone):
    clean = clean_phone(phone)
    try:
        r = requests.get(f"https://t.me/{clean}", timeout=3)
        return "✅ Найден" if r.status_code == 200 else "❌ Не найден"
    except:
        return "⚠️ Ошибка проверки"

def check_viber(phone):
    clean = clean_phone(phone)
    try:
        r = requests.get(f"https://viber.com/ru/{clean}", timeout=3, allow_redirects=True)
        if "viber" in r.url and "login" not in r.url:
            return "✅ Найден"
        return "❌ Не найден"
    except:
        return "⚠️ Ошибка проверки"

def get_phone_info(phone):
    report = {"info": {}, "whatsapp": "❌ Неизвестно", "telegram": "❌ Неизвестно", "viber": "❌ Неизвестно", "leaks": []}
    
    # 1. htmlweb.ru (гео + оператор)
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
    report["whatsapp"] = check_whatsapp(phone)
    
    # 3. Telegram
    report["telegram"] = check_telegram(phone)
    
    # 4. Viber
    report["viber"] = check_viber(phone)
    
    # 5. Leakcheck (утечки)
    clean = clean_phone(phone)
    try:
        r = requests.get(f"https://leakcheck.io/search?q={clean}", timeout=5)
        if r.status_code == 200:
            bases = re.findall(r'<td>(.*?)</td>\s*<td>(.*?)</td>', r.text)
            report["leaks"] = [{"База": b[0].strip(), "Дата": b[1].strip()} for b in bases[:5]]
    except:
        pass
    
    return report

# ---------- ОТПРАВКА СООБЩЕНИЙ ----------
def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "reply_markup": reply_markup
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def send_typing(chat_id):
    url = f"https://api.telegram.org/bot{TOKEN}/sendChatAction"
    try:
        requests.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=2)
    except:
        pass

# ---------- ФОРМАТИРОВАНИЕ ОТЧЁТА ----------
def format_report(phone, report):
    answer = f"📱 *Номер:* `{phone}`\n"
    if report["info"]:
        for k, v in report["info"].items():
            answer += f"• *{k}:* {v}\n"
    answer += f"• *WhatsApp:* {report['whatsapp']}\n"
    answer += f"• *Telegram:* {report['telegram']}\n"
    answer += f"• *Viber:* {report['viber']}\n"
    if report["leaks"]:
        answer += "🔓 *Утечки:*\n"
        for leak in report["leaks"][:3]:
            answer += f"  - {leak['База']} ({leak['Дата']})\n"
    else:
        answer += "✅ Утечек не найдено"
    return answer

# ---------- КЛАВИАТУРА ----------
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📱 Проверить номер", "callback_data": "check_phone"}],
            [{"text": "🆘 Помощь", "callback_data": "help"}]
        ]
    }

# ---------- ОБРАБОТЧИК ОБНОВЛЕНИЙ ----------
def handle_update(update):
    # Обработка callback-запросов (кнопки)
    if "callback_query" in update:
        query = update["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        data = query["data"]
        
        if data == "check_phone":
            send_message(chat_id, "📲 Отправь номер в формате +79123456789")
        elif data == "help":
            send_message(chat_id, "📌 *Инструкция*\nОтправь номер в формате +79123456789\nЯ покажу страну, оператора, статус в мессенджерах и утечки.", parse_mode="Markdown")
        return
    
    if "message" not in update:
        return
    
    message = update["message"]
    chat_id = message["chat"]["id"]
    if "text" not in message:
        return
    
    text = message["text"].strip()
    
    # Команды
    if text.startswith('/'):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if cmd == '/start':
            send_message(chat_id, 
                "👋 Привет! Я помогу проверить номер телефона.\nОтправь номер в формате +79123456789\nИли используй /phone +79123456789",
                reply_markup=get_main_keyboard()
            )
            return
        elif cmd == '/help':
            send_message(chat_id, 
                "📌 *Инструкция*\n• Отправь номер в формате +79123456789\n• Или /phone +79123456789\nЯ покажу страну, оператора, статус в WhatsApp/Telegram/Viber и утечки.",
                parse_mode="Markdown"
            )
            return
        elif cmd == '/phone':
            if arg and re.match(r'^\+?\d{10,15}$', arg):
                send_typing(chat_id)
                report = get_phone_info(arg)
                answer = format_report(arg, report)
                send_message(chat_id, answer, parse_mode="Markdown")
            else:
                send_message(chat_id, "❌ Укажи номер после команды, например: /phone +79123456789")
            return
        else:
            send_message(chat_id, "❌ Неизвестная команда. Используй /start или /help")
            return
    
    # Если не команда — пробуем как номер
    if not re.match(r'^\+?\d{10,15}$', text):
        send_message(chat_id, "❌ Отправь номер в формате +79123456789")
        return
    
    send_typing(chat_id)
    report = get_phone_info(text)
    answer = format_report(text, report)
    send_message(chat_id, answer, parse_mode="Markdown")

# ---------- ОСНОВНОЙ ЦИКЛ ПОЛЛИНГА ----------
def bot_polling():
    offset = 0
    print("✅ Bot polling started")
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
    threading.Thread(target=run_flask, daemon=True).start()
    bot_polling()

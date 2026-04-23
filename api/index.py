from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import traceback

TOKEN = "8269135710:AAE9mv55_QJOg3VN6U7JploC6KqigKBZf6Y"
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"

DB_FILE = "/tmp/database.json"
STATE_FILE = "/tmp/user_states.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"masters": {}, "appointments": []}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_states():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_states(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    requests.post(f"{TELEGRAM_URL}/sendMessage", json=payload)

# === КЛАВИАТУРЫ ===
def master_menu():
    return {
        "keyboard": [
            ["📅 Моё расписание", "➕ Новая запись"],
            ["👥 Клиенты", "📊 Статистика"],
            ["⚙️ Настройки"]
        ],
        "resize_keyboard": True
    }

def settings_menu():
    return {
        "keyboard": [
            ["💈 Мои услуги", "⏰ Рабочие часы"],
            ["🔙 Назад в меню"]
        ],
        "resize_keyboard": True
    }

def services_inline(services):
    buttons = []
    for s in services:
        buttons.append([{"text": f"❌ {s}", "callback_data": f"del_service_{s}"}])
    buttons.append([{"text": "➕ Добавить услугу", "callback_data": "add_service"}])
    buttons.append([{"text": "🔙 Назад", "callback_data": "back_to_settings"}])
    return {"inline_keyboard": buttons}

# === ОБРАБОТЧИКИ ===
def handle_start(chat_id, user_name):
    db = load_db()
    if str(chat_id) in db["masters"]:
        send_message(chat_id, f"С возвращением, мастер {user_name}!", reply_markup=master_menu())
    else:
        keyboard = {
            "keyboard": [["👤 Я мастер", "👥 Я клиент"]],
            "resize_keyboard": True
        }
        send_message(chat_id, "👋 Добро пожаловать в *График.Про*!\n\nЯ помогу записывать клиентов и не терять деньги.\n\n*Кто вы?*", reply_markup=keyboard)

def handle_master_registration(chat_id, user_name, username):
    db = load_db()
    db["masters"][str(chat_id)] = {
        "name": user_name,
        "username": username,
        "services": [],
        "registered_at": "now"
    }
    save_db(db)
    send_message(chat_id, "✅ Вы зарегистрированы как мастер!\n\n⚙️ *Рекомендуем сразу настроить список услуг.*", reply_markup=master_menu())

def handle_settings_services(chat_id):
    db = load_db()
    master = db["masters"].get(str(chat_id))
    if not master:
        send_message(chat_id, "Сначала зарегистрируйтесь как мастер.")
        return
    
    services = master.get("services", [])
    if services:
        text = "💈 *Ваши услуги:*\nНажмите на услугу, чтобы удалить её.\nИли добавьте новую."
    else:
        text = "💈 *У вас пока нет услуг.*\nНажмите кнопку ниже, чтобы добавить."
    send_message(chat_id, text, reply_markup=services_inline(services))

def handle_add_service_prompt(chat_id):
    states = load_states()
    states[str(chat_id)] = {"state": "adding_service"}
    save_states(states)
    keyboard = {"keyboard": [["🔙 Отмена"]], "resize_keyboard": True}
    send_message(chat_id, "✏️ *Введите название услуги:*\nНапример: «Стрижка машинкой», «Маникюр с гель-лаком»", reply_markup=keyboard)

def handle_add_service_name(chat_id, service_name):
    db = load_db()
    master = db["masters"].get(str(chat_id))
    if not master:
        return
    if "services" not in master:
        master["services"] = []
    master["services"].append(service_name)
    save_db(db)
    
    states = load_states()
    if str(chat_id) in states:
        del states[str(chat_id)]
        save_states(states)
    
    send_message(chat_id, f"✅ Услуга *«{service_name}»* добавлена!", reply_markup=settings_menu())
    handle_settings_services(chat_id)

def handle_delete_service(chat_id, service_name):
    db = load_db()
    master = db["masters"].get(str(chat_id))
    if master and "services" in master:
        master["services"] = [s for s in master["services"] if s != service_name]
        save_db(db)
    send_message(chat_id, f"🗑 Услуга *«{service_name}»* удалена.")
    handle_settings_services(chat_id)

def handle_text(chat_id, user_name, username, text):
    db = load_db()
    states = load_states()
    
    # Проверка на состояние
    user_state = states.get(str(chat_id), {}).get("state")
    if user_state == "adding_service":
        if text == "🔙 Отмена":
            states.pop(str(chat_id), None)
            save_states(states)
            send_message(chat_id, "❌ Добавление отменено.", reply_markup=settings_menu())
        else:
            handle_add_service_name(chat_id, text)
        return
    
    # Основные команды
    if text == "👤 Я мастер":
        if str(chat_id) in db["masters"]:
            send_message(chat_id, "Вы уже зарегистрированы!", reply_markup=master_menu())
        else:
            handle_master_registration(chat_id, user_name, username)
    
    elif text == "👥 Я клиент":
        send_message(chat_id, "🔍 Раздел клиента в разработке.", reply_markup=client_menu())
    
    elif text == "⚙️ Настройки":
        send_message(chat_id, "⚙️ *Настройки профиля*", reply_markup=settings_menu())
    
    elif text == "💈 Мои услуги":
        handle_settings_services(chat_id)
    
    elif text == "⏰ Рабочие часы":
        send_message(chat_id, "⏰ Настройка рабочего времени появится в следующем обновлении.")
    
    elif text == "🔙 Назад в меню":
        send_message(chat_id, "🔙 Главное меню", reply_markup=master_menu())
    
    elif text == "📅 Моё расписание":
        send_message(chat_id, "📭 На этой неделе записей пока нет.")
    
    elif text == "➕ Новая запись":
        send_message(chat_id, "📝 Попросите клиента написать боту. Эта функция скоро появится.")
    
    elif text == "👥 Клиенты":
        send_message(chat_id, "👥 Список клиентов пока пуст.")
    
    elif text == "📊 Статистика":
        send_message(chat_id, "📊 Статистика будет здесь после первых записей.")
    
    else:
        send_message(chat_id, "Используйте кнопки меню.", reply_markup=master_menu())

def handle_callback(chat_id, data):
    if data == "add_service":
        handle_add_service_prompt(chat_id)
    elif data.startswith("del_service_"):
        service_name = data.replace("del_service_", "", 1)
        handle_delete_service(chat_id, service_name)
    elif data == "back_to_settings":
        send_message(chat_id, "⚙️ *Настройки профиля*", reply_markup=settings_menu())

def process_update(update):
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_name = msg["from"].get("first_name", "Пользователь")
        username = msg["from"].get("username", "")
        
        if "text" in msg:
            text = msg["text"]
            if text.startswith("/start"):
                handle_start(chat_id, user_name)
            else:
                handle_text(chat_id, user_name, username, text)
    
    elif "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb["data"]
        handle_callback(chat_id, data)

# === СЕРВЕР ===
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length else b''
        try:
            update = json.loads(post_data.decode('utf-8'))
            process_update(update)
        except Exception as e:
            print(f"Error: {e}\n{traceback.format_exc()}")
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "bot online"}).encode())
import os
import json
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# 🔥 Отримання змінних середовища
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Якщо ADMIN_ID не встановлено, використовується 0

# 🔥 Перевірка змінних перед запуском
if not TOKEN:
    raise ValueError("❌ Помилка: змінна середовища BOT_TOKEN не встановлена!")

if ADMIN_ID == 0:
    print("⚠️ Попередження: ADMIN_ID не встановлено. Бот працюватиме без адміністратора.")

# 🔥 Ініціалізація Firebase через змінну середовища
firebase_credentials_str = os.getenv("FIREBASE_CREDENTIALS")

if not firebase_credentials_str:
    raise ValueError("❌ Помилка: змінна середовища FIREBASE_CREDENTIALS не встановлена!")

try:
    FIREBASE_JSON = json.loads(firebase_credentials_str)
except json.JSONDecodeError:
    raise ValueError("❌ Помилка: Неправильний формат JSON у FIREBASE_CREDENTIALS!")

cred = credentials.Certificate(FIREBASE_JSON)
firebase_admin.initialize_app(cred)
db = firestore.client()

# 🔥 Ініціалізація Telegram-бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# 📌 **Головне меню**
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📋 Меню")]],
    resize_keyboard=True
)

# 📌 **Отримання списку сайтів**
def get_sites():
    requests_ref = db.collection("requests")
    docs = requests_ref.stream()
    sites = set()

    for doc in docs:
        data = doc.to_dict()
        sites.add(data.get("site", "Невідомий сайт"))

    return list(sites)

# 📌 **Отримання заявок для сайту**
def get_requests_by_site(site, status=None):
    requests_ref = db.collection("requests").where("site", "==", site)
    if status:
        requests_ref = requests_ref.where("status", "==", status)

    docs = requests_ref.stream()
    
    phone_requests = []
    chat_requests = []

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if data.get("phone") and data["phone"] != "не вказано":
            phone_requests.append(data)
        elif data.get("social") and data["social"] != "не вказано":
            chat_requests.append(data)

    return phone_requests, chat_requests

# 📌 **Команда /start**
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🔹 Вітаю! Я бот для керування заявками.\n\nℹ Натисніть 📋 Меню, щоб переглянути заявки.", reply_markup=main_menu)

# 📌 **Команда /menu (показує список сайтів)**
@dp.message(lambda message: message.text == "📋 Меню" or message.text == "/menu")
async def menu(message: types.Message):
    sites = get_sites()
    if not sites:
        await message.answer("⚠️ Жоден сайт ще не надсилав заявки.")
        return

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=site, callback_data=f"site|{site}")] for site in sites
        ]
    )
    await message.answer("📌 Оберіть сайт, щоб переглянути заявки:", reply_markup=markup)

# 📌 **Обробка вибору сайту**
@dp.callback_query(lambda c: c.data.startswith("site|"))
async def show_site_options(callback_query: types.CallbackQuery):
    site = callback_query.data.split("|")[1]

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📞 Передзвонити", callback_data=f"phone|{site}")],
            [InlineKeyboardButton(text="💬 Написати в чат", callback_data=f"chat|{site}")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="menu")]
        ]
    )
    await callback_query.message.delete()
    await callback_query.message.answer(f"📌 <b>{site}</b>\nОберіть тип заявок:", reply_markup=markup)

# 📌 **Запуск бота**
async def main():
    print("🔄 Запуск бота...")
    print(f"✅ Бот працює! Очікування повідомлень...\n👨‍💻 Адмін ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import json
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# 🔥 Токен бота та ID адміна
TOKEN = "7711059163:AAHWNiFfmUzvV3ViPSsdGJl-GgQdaq8ucus"  # 🔥 Замінити на свій токен
ADMIN_ID = 1446641391  # 🔥 Замінити на свій Telegram ID

# 🔥 Ініціалізація Firebase
cred = credentials.Certificate("firebase_credentials.json")  # 🔥 Замінити на свій JSON-файл з ключем
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

# 📌 **Обробка вибору категорії "Передзвонити"**
@dp.callback_query(lambda c: c.data.startswith("phone|"))
async def show_phone_status_options(callback_query: types.CallbackQuery):
    site = callback_query.data.split("|")[1]

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Не виконані", callback_data=f"phone_requests|{site}|new")],
            [InlineKeyboardButton(text="✅ Виконані", callback_data=f"phone_requests|{site}|done")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data=f"site|{site}")]
        ]
    )
    await callback_query.message.delete()
    await callback_query.message.answer(f"📞 <b>{site}</b>\nОберіть статус заявок:", reply_markup=markup)

# 📌 **Обробка вибору категорії "Написати в чат"**
@dp.callback_query(lambda c: c.data.startswith("chat|"))
async def show_chat_status_options(callback_query: types.CallbackQuery):
    site = callback_query.data.split("|")[1]

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟡 Не виконані", callback_data=f"chat_requests|{site}|new")],
            [InlineKeyboardButton(text="✅ Виконані", callback_data=f"chat_requests|{site}|done")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data=f"site|{site}")]
        ]
    )
    await callback_query.message.delete()
    await callback_query.message.answer(f"💬 <b>{site}</b>\nОберіть статус заявок:", reply_markup=markup)

# 📌 **Відображення заявок**
@dp.callback_query(lambda c: c.data.startswith("phone_requests|") or c.data.startswith("chat_requests|"))
async def show_requests(callback_query: types.CallbackQuery):
    _, site, status = callback_query.data.split("|")
    phone_requests, chat_requests = get_requests_by_site(site, status)

    requests = phone_requests if "phone_requests" in callback_query.data else chat_requests

    await callback_query.message.delete()

    if not requests:
        await callback_query.message.answer(f"⚠️ На сайті {site} немає {'виконаних' if status == 'done' else 'невиконаних'} заявок.")
        return

    for req in requests:
        await send_request_card(callback_query.message, req)

    menu_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад", callback_data=f"{'phone' if 'phone_requests' in callback_query.data else 'chat'}|{site}")]
        ]
    )
    await callback_query.message.answer("📌 Оберіть дію:", reply_markup=menu_markup)

# 📌 **Відправка заявки у вигляді карточки**
async def send_request_card(message, req):
    text = (
        f"📌 <b>Заявка</b>\n"
        f"🌍 <b>Сайт:</b> {req['site']}\n"
        f"📞 <b>Телефон:</b> {req['phone']}\n"
        f"🔗 <b>{req['social']}:</b> {req['nickname']}\n"
        f"🟢 <b>Статус:</b> {'✅ Виконано' if req.get('status') == 'done' else '🟡 Не виконано'}"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Виконано", callback_data=f"done|{req['id']}")],
            [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"delete|{req['id']}")]
        ]
    )
    await bot.send_message(message.chat.id, text, reply_markup=markup)

# 📌 **Запуск бота**
async def main():
    print("🔄 Запуск бота...")
    print("✅ Бот працює! Очікування повідомлень...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

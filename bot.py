import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
    FSInputFile  # <-- Fayllarni local xotiradan yuborish uchun import qilindi
)
from google import genai
from google.genai import types
import database as db
db.init_db()  # <-- database.py dagi jadval yaratuvchi funksiya nomi

BOT_TOKEN = "8890889822:AAGLGLOh5qsvbumkMR8xwe537mawUj-BdG4"
GOOGLE_API_KEY = "AQ.Ab8RN6J9C9RPbdCdq2fdI-AeBbN23z1doEHU9I9N5v_fuCG5ww"


REQUIRED_CHANNELS = ["@harward_go"]  

google_client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Lessons ma'lumotlarini yuklash
with open("lessons_data.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)

# ---------- Yordamchi Funksiyalar (Obuna & Xabarlar) ----------
async def check_sub_channels(bot_instance: Bot, user_id: int) -> list:
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot_instance.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                not_subscribed.append(channel)
        except Exception as e:
            logging.error(f"Kanalni tekshirishda xatolik: {e}")
    return not_subscribed

def build_sub_keyboard(not_subscribed_channels: list):
    buttons = []
    for i, ch in enumerate(not_subscribed_channels, start=1):
        clean_ch = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text=f"📢 {i}-kanalga a'zo bo'lish", url=f"https://t.me/{clean_ch}")])
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def track_message(state: FSMContext, msg_id: int):
    """Registratsiya davomidagi xabar ID-larini xotirada saqlaydi."""
    data = await state.get_data()
    msg_ids = data.get("msg_ids", [])
    msg_ids.append(msg_id)
    await state.update_data(msg_ids=msg_ids)

async def delete_saved_messages(bot_instance: Bot, chat_id: int, state: FSMContext):
    """Saqlangan barcha registratsiya xabarlarini o'chirib tashlaydi."""
    data = await state.get_data()
    msg_ids = data.get("msg_ids", [])
    for msg_id in msg_ids:
        try:
            await bot_instance.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

def get_subject(subject_id):
    for s in DATA.get("fanlar", []):
        if s["id"] == subject_id:
            return s
    return None

def get_lesson(subject_id, lesson_id):
    subject = get_subject(subject_id)
    if not subject:
        return None
    for l in subject.get("darslar", []):
        if l["id"] == lesson_id:
            return l
    return None

# ---------- Registratsiya va AI Shtatlari ----------
class RegisterStates(StatesGroup):
    grade = State()
    school = State()
    region = State()
    age = State()
    weak_subjects = State()
    free_hours = State()
    phone = State()
    password = State()

class AIStates(StatesGroup):
    waiting_for_question = State()

# ---------- Menyular ----------
def build_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎓 Fanlar", callback_data="show_subjects")],
            [InlineKeyboardButton(text="📘 SAT tayyorlov", callback_data="show_sat")],
            [InlineKeyboardButton(text="🤖 AI maslahatchi", callback_data="show_ai")],
            [InlineKeyboardButton(text="👤 Profil", callback_data="show_profile")],
            [InlineKeyboardButton(text="🏆 Reyting", callback_data="show_rating")],
            [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="settings")],
        ]
    )

def build_subject_menu():
    regular_subjects = [s for s in DATA.get("fanlar", []) if not s["id"].startswith("sat_")]
    buttons = [
        [InlineKeyboardButton(text=s["name"], callback_data=f"subject_{s['id']}")]
        for s in regular_subjects
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- /start va Majburiy Obuna Handlerlari ----------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    not_subbed = await check_sub_channels(bot, message.from_user.id)
    if not_subbed:
        await message.answer(
            "⚠️ **Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:**\n\n"
            "Kanallarga obuna bo'lgach, **'✅ Obunani tekshirish'** tugmasini bosing.",
            reply_markup=build_sub_keyboard(not_subbed)
        )
        return

    is_new = db.add_user(message.from_user.id, message.from_user.full_name)
    await state.clear()
    
    if is_new:
        q_msg = await message.answer(
            f"Salom, {message.from_user.full_name}! 👋\n\n"
            "Botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n"
            "1️⃣ Nechanchi sinfdasiz? (Masalan: 9)"
        )
        await track_message(state, message.message_id)
        await track_message(state, q_msg.message_id)
        await state.set_state(RegisterStates.grade)
        return

    await message.answer(
        f"Xush kelibsiz, {message.from_user.full_name}!\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=build_main_menu(),
    )

@router.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    not_subbed = await check_sub_channels(bot, callback.from_user.id)
    if not_subbed:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
    else:
        await callback.message.delete()
        await callback.answer("✅ Rahmat, barcha kanallarga obuna bo'ldingiz!")
        await cmd_start(callback.message, state, bot)

# ---------- Registratsiya Bosqichlari ----------
@router.message(RegisterStates.grade)
async def process_grade(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    if not message.text or not message.text.isdigit():
        q_msg = await message.answer("Iltimos, sinf raqamini faqat son bilan kiriting. Masalan: 9")
        await track_message(state, q_msg.message_id)
        return
    await state.update_data(grade=int(message.text))
    q_msg = await message.answer("2️⃣ Qaysi maktabda o'qiysiz? (Masalan: 14-maktab)")
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.school)

@router.message(RegisterStates.school)
async def process_school(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    await state.update_data(school=message.text.strip())
    q_msg = await message.answer("3️⃣ Qaysi viloyat yoki shahardansiz? (Masalan: Toshkent)")
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.region)

@router.message(RegisterStates.region)
async def process_region(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    await state.update_data(region=message.text.strip())
    q_msg = await message.answer("4️⃣ Nechanchi yoshdasiz? (Masalan: 15)")
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.age)

@router.message(RegisterStates.age)
async def process_age(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    if not message.text or not message.text.isdigit():
        q_msg = await message.answer("Iltimos, yoshingizni son bilan kiriting. Masalan: 15")
        await track_message(state, q_msg.message_id)
        return
    await state.update_data(age=int(message.text))
    q_msg = await message.answer("5️⃣ Qaysi fanlardan ko'proq qiynalasiz? (Masalan: Matematika, Fizika)")
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.weak_subjects)

@router.message(RegisterStates.weak_subjects)
async def process_weak_subjects(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    await state.update_data(weak_subjects=message.text.strip())
    q_msg = await message.answer("6️⃣ Kuniga nechta soat bo'sh vaqtingiz bor? (Masalan: 2 soat)")
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.free_hours)

@router.message(RegisterStates.free_hours)
async def process_free_hours(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    await state.update_data(free_hours=message.text.strip())
    
    phone_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    q_msg = await message.answer("7️⃣ Telefon raqamingizni pastdagi tugma orqali yuboring:", reply_markup=phone_kb)
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.phone)

@router.message(RegisterStates.phone, F.contact | F.text)
async def process_phone(message: Message, state: FSMContext):
    await track_message(state, message.message_id)
    phone_num = message.contact.phone_number if message.contact else message.text.strip()
        
    await state.update_data(phone=phone_num)
    q_msg = await message.answer(
        "8️⃣ Hisobingiz uchun maxfiy parol yarating va yozing:\n(Ushbu parol profilingiz xavfsizligi uchun kerak)",
        reply_markup=ReplyKeyboardRemove()
    )
    await track_message(state, q_msg.message_id)
    await state.set_state(RegisterStates.password)

@router.message(RegisterStates.password)
async def process_password(message: Message, state: FSMContext, bot: Bot):
    await track_message(state, message.message_id)
    password = message.text.strip()
    data = await state.get_data()
    
    db.update_full_profile(
        message.from_user.id,
        data.get("grade"),
        data.get("school"),
        data.get("region"),
        data.get("age"),
        data.get("weak_subjects"),
        data.get("free_hours"),
        data.get("phone"),
        password
    )
    
    await delete_saved_messages(bot, message.chat.id, state)
    
    await message.answer(
        "✅ **Registratsiya muvaffaqiyatli yakunlandi!**\n\n"
        "Barcha ma'lumotlaringiz saqlandi. Endi bo'limlardan foydalanishingiz mumkin:",
        reply_markup=build_main_menu()
    )
    await state.clear()

# ---------- Profil ----------
@router.callback_query(F.data == "show_profile")
@router.message(Command("profil"))
async def show_profile(event):
    user_id = event.from_user.id
    user, lessons_done = db.get_user_stats(user_id)
    
    if not user:
        msg = "Avval /start bosing va ro'yxatdan o'ting."
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg)
            await event.answer()
        else:
            await event.answer(msg)
        return

    name, score, level, streak, grade, school, region, age, weak_subjects, free_hours, phone = user
    
    profile_text = (
        f"👤 **Profil:** {name}\n"
        f"📱 **Tel:** {phone or 'Kiritilmagan'}\n"
        f"🎓 **Sinf:** {grade or 'Kiritilmagan'}-sinf\n"
        f"🏫 **Maktab:** {school or 'Kiritilmagan'}\n"
        f"📍 **Manzil:** {region or 'Kiritilmagan'}\n"
        f"🎂 **Yosh:** {age or 'Kiritilmagan'}\n"
        f"📚 **Qiynalayotgan fanlar:** {weak_subjects or 'Yo‘q'}\n"
        f"⏳ **Kunlik bo'sh vaqt:** {free_hours or 'Kiritilmagan'}\n"
        f"-----------------------------\n"
        f"✅ **Tugatilgan darslar:** {lessons_done}\n"
        f"⭐ **Umumiy ball:** {score}\n"
        f"🏅 **Daraja:** {level}\n"
        f"🔥 **Kunlik streak:** {streak or 0}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="main_menu")]])
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(profile_text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(profile_text, reply_markup=kb)

# ---------- AI Maslahatchi Bo'limi ----------
@router.callback_query(F.data == "show_ai")
async def show_ai(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AIStates.waiting_for_question)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text(
        "🤖 **AI Maslahatchi bo'limi**\n\n"
        "Menga ta'lim, fanlar yoki o'qish rejangiz bo'yicha istalgan savolingizni berishingiz mumkin. "
        "Savolingizni yuboring:",
        reply_markup=kb,
    )
    await callback.answer()

@router.message(AIStates.waiting_for_question)
async def process_ai_question(message: Message, state: FSMContext):
    user_prompt = message.text
    loading_msg = await message.answer("🤔 AI o'ylanmoqda, biroz kuting...")

    if google_client is None:
        await loading_msg.edit_text(
            "❌ Google AI Studio API kaliti sozlanmagan. "
            "Botni ishga tushirishdan oldin GOOGLE_API_KEY ni kiriting."
        )
        return

    try:
        response = await google_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Siz o'quvchilarga ta'lim va o'qishda yordam beradigan aqlli, "
                    "do'stona va bilimdon AI maslahatchisisiz. Javoblaringizni "
                    "o'zbek tilida, aniq va tushunarli qilib bering."
                )
            ),
        )
        answer_text = response.text
        if not answer_text:
            raise ValueError("Google AI Studio bo'sh javob qaytardi")
        await loading_msg.edit_text(answer_text)
    except Exception as e:
        logging.error(f"Google AI Studio error: {e}")
        await loading_msg.edit_text("❌ Javob olishda xatolik yuz berdi. Qayta urinib ko'ring.")

# ---------- SAT Tayyorlov va Kitob Yuborish Bo'limi ----------
@router.callback_query(F.data == "show_sat")
async def show_sat(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📐 SAT Math", callback_data="subject_sat_math")],
            [InlineKeyboardButton(text="📖 SAT Reading & Writing", callback_data="subject_sat_rw")],
            [InlineKeyboardButton(text="📚 SAT Tayyorlov Kitobi (PDF)", callback_data="send_sat_book")], # <-- Yangi qo'shilgan kitob tugmasi
            [InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text("📘 **SAT Tayyorlov bo'limi**\n\nYo'nalishni tanlang:", reply_markup=kb)
    await callback.answer()

from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

# 📌 SAT Math tugmasi bosilganda kitob yuborish
@router.callback_query(F.data == "send_sat_book")  # callback_data tugmangizniki bilan bir xil bo'lsin
async def send_sat_book(callback: CallbackQuery):
    # 1. Tepada bildirishnoma chiqarish
    await callback.answer("📖 Kitob yuborilmoqda...")
    
    # 2. Fayl yo'lini belgilaymiz
    file_path = "The College Panda SAT Math.pdf"
    
    # 3. Fayl mavjudligini va yuborilishini tekshiramiz
    if os.path.exists(file_path):
        document = FSInputFile(file_path, filename="The_College_Panda_SAT_Math.pdf")
        
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="show_sat")]
            ]
        )
        
        # Chatga faylni yuborish
        await callback.message.answer_document(
            document=document,
            caption="📘 **The College Panda SAT Math** kitobi!\n\nMuvaffaqiyatli yuklab olindi.",
            reply_markup=kb
        )
    else:
        # Fayl topilmasa xabar berish
        await callback.message.answer(
            "⚠️ **Xatolik:** Kitob fayli topilmadi. Fayl nomi to'g'riligini tekshiring."
        )

# ---------- Botning Boshqa Menyulari ----------
@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Quyidagi bo'limlardan birini tanlang:", reply_markup=build_main_menu())
    await callback.answer()

@router.callback_query(F.data == "show_subjects")
async def show_subjects(callback: CallbackQuery):
    await callback.message.edit_text("Fanlardan birini tanlang:", reply_markup=build_subject_menu())
    await callback.answer()

@router.callback_query(F.data == "show_rating")
async def show_rating_cb(callback: CallbackQuery):
    rows = db.get_leaderboard()
    text = "🏆 Reyting (TOP 10):\n\n"
    if not rows:
        text += "Hozircha hech kim yo'q."
    for i, (name, score) in enumerate(rows, start=1):
        text += f"{i}. {name} — {score} ball\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Sozlamalar bo'limi tez orada ishga tushadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="main_menu")]])
    )
    await callback.answer()

# ---------- Asosiy Ishga Tushirish Funksiyasi ----------
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

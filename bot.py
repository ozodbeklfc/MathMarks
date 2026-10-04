"""Telegram bot: setup commands, Excel import and export. All texts are in Uzbek."""
import io
from datetime import date

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BotCommand, BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo)

import config
import excel
import services
from db import Session

teacher = Router()
teacher.message.filter(F.from_user.id.in_(config.TEACHER_IDS))
teacher.callback_query.filter(F.from_user.id.in_(config.TEACHER_IDS))
others = Router()


class AddClass(StatesGroup):
    name = State()


class AddMembers(StatesGroup):
    names = State()
    confirm = State()


HELP = (
    "Buyruqlar:\n"
    "/add_class — yangi sinf qo'shish\n"
    "/add_class_members — sinfga o'quvchilar ro'yxatini qo'shish\n"
    "/classes — sinflar ro'yxati\n"
    "/import — Excel fayldan yuklash\n"
    "/export — Excel faylga chiqarish\n"
    "/cancel — bekor qilish"
)


def open_app_kb():
    if not config.WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📒 Jurnalni ochish", web_app=WebAppInfo(url=config.WEBAPP_URL))]])


@teacher.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Bu — baholar jurnali.\n\n"
        "Mavzularni kiritish va baho qo'yish uchun jurnalni oching.\n\n" + HELP,
        reply_markup=open_app_kb())


@teacher.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


@teacher.message(Command("add_class"))
async def add_class(message: Message, state: FSMContext):
    await state.set_state(AddClass.name)
    await message.answer("Sinf nomini yuboring. Masalan: 6-02(1)")


@teacher.message(AddClass.name, F.text, ~F.text.startswith("/"))
async def add_class_name(message: Message, state: FSMContext):
    with Session() as s:
        cls = services.add_class(s, message.text[:64])
        s.commit()
    await state.clear()
    await message.answer(
        f"✅ «{cls.name}» sinfi tayyor.\nO'quvchilarni qo'shish uchun: /add_class_members")


@teacher.message(Command("add_class_members"))
async def add_members(message: Message, state: FSMContext):
    with Session() as s:
        classes = services.list_classes(s)
    if not classes:
        await message.answer("Hali sinf yo'q. Avval /add_class buyrug'i bilan sinf qo'shing.")
        return
    await state.clear()
    rows = [[InlineKeyboardButton(text=c.name, callback_data=f"cls:{c.id}")] for c in classes]
    await message.answer("Qaysi sinfga o'quvchi qo'shamiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@teacher.callback_query(F.data.startswith("cls:"))
async def members_class(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddMembers.names)
    await state.update_data(class_id=int(cb.data.split(":")[1]))
    await cb.message.answer("O'quvchilar ro'yxatini yuboring: har bir ism-familiya alohida qatorda.")
    await cb.answer()


@teacher.message(AddMembers.names, F.text, ~F.text.startswith("/"))
async def members_names(message: Message, state: FSMContext):
    names = services.parse_names(message.text)
    if not names:
        await message.answer("Ro'yxatni o'qib bo'lmadi. Har bir ismni alohida qatorga yozing.")
        return
    await state.update_data(names=names)
    await state.set_state(AddMembers.confirm)
    listing = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Saqlash", callback_data="members:save"),
        InlineKeyboardButton(text="✖️ Bekor qilish", callback_data="members:cancel")]])
    await message.answer(f"{len(names)} ta o'quvchi:\n\n{listing}\n\nSaqlaymizmi?", reply_markup=kb)


@teacher.callback_query(AddMembers.confirm, F.data.startswith("members:"))
async def members_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if cb.data.endswith("cancel"):
        await cb.message.edit_text("Bekor qilindi.")
    else:
        with Session() as s:
            added = services.add_students(s, data["class_id"], data["names"])
            s.commit()
        skipped = len(data["names"]) - added
        text = f"✅ {added} ta o'quvchi qo'shildi."
        if skipped:
            text += f" {skipped} tasi ro'yxatda bor edi."
        await cb.message.edit_text(text)
    await cb.answer()


@teacher.message(Command("classes"))
async def classes(message: Message):
    with Session() as s:
        summary = services.classes_summary(s)
    if not summary:
        await message.answer("Hali sinf yo'q. /add_class yoki /import dan boshlang.")
        return
    lines = [f"• {c['name']} — {c['students']} o'quvchi, {c['topics']} mavzu, o'rtacha {c['avg']} / {c['max']} ball"
             for c in summary]
    await message.answer("Sinflar:\n" + "\n".join(lines), reply_markup=open_app_kb())


@teacher.message(Command("import"))
async def import_help(message: Message):
    await message.answer(
        "Excel faylni (.xlsx) shu yerga yuboring.\n"
        "Har bir varaq — alohida sinf. Shu nomli sinf bor bo'lsa, u fayldagi ma'lumot bilan almashtiriladi.")


@teacher.message(F.document)
async def import_file(message: Message, bot: Bot):
    if not (message.document.file_name or "").lower().endswith(".xlsx"):
        await message.answer("Faqat .xlsx fayl qabul qilinadi.")
        return
    buf = io.BytesIO()
    await bot.download(message.document, destination=buf)
    try:
        with Session() as s:
            report = excel.import_workbook(s, buf.getvalue())
            s.commit()
    except Exception as e:  # a broken file must not stop the bot
        await message.answer(f"Faylni o'qib bo'lmadi: {e}")
        return
    if not report:
        await message.answer("Faylda sinf topilmadi.")
        return
    lines = [f"• {r['class']} — {r['students']} o'quvchi, {r['topics']} mavzu, {r['marks']} baho" for r in report]
    await message.answer("✅ Yuklandi:\n" + "\n".join(lines), reply_markup=open_app_kb())


@teacher.message(Command("export"))
async def export(message: Message):
    with Session() as s:
        data = excel.export_workbook(s)
    await message.answer_document(BufferedInputFile(data, filename=f"Baholar_{date.today():%Y-%m-%d}.xlsx"))


@teacher.message()
async def fallback(message: Message):
    await message.answer(HELP, reply_markup=open_app_kb())


@others.message()
async def not_teacher(message: Message):
    await message.answer(
        "Bu bot hozircha faqat o'qituvchi uchun.\n"
        f"Sizning Telegram ID: {message.from_user.id}")


async def run_bot():
    bot = Bot(config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_routers(teacher, others)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands([
        BotCommand(command="start", description="Jurnalni ochish"),
        BotCommand(command="add_class", description="Sinf qo'shish"),
        BotCommand(command="add_class_members", description="O'quvchilar ro'yxatini qo'shish"),
        BotCommand(command="classes", description="Sinflar ro'yxati"),
        BotCommand(command="import", description="Excel fayldan yuklash"),
        BotCommand(command="export", description="Excel faylga chiqarish"),
    ])
    if config.WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Jurnal", web_app=WebAppInfo(url=config.WEBAPP_URL)))
    await dp.start_polling(bot, handle_signals=False)

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from ..config import get_settings
from ..db import Base, engine, SessionLocal
from ..repo import create_note, list_notes, count_notes, get_note, delete_note, update_note
from .keyboards import main_menu, notes_list_kb, note_view_kb

# ---- Константы ----
PAGE_SIZE = 5
AWAITING_NEW, AWAITING_EDIT = range(2)  # состояния диалога


# ---- Инициализация БД ----
def init_db():
    Base.metadata.create_all(bind=engine)


# ---- Главное меню ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Это простой бот-заметочник.\n\n"
        "• 📝 Создавай заметки\n"
        "• 📚 Храни сколько угодно\n"
        "• 🔍 Просматривай, редактируй, удаляй\n\n"
        "Нажми кнопку ниже."
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu())


async def home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Главное меню:", reply_markup=main_menu())


async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        "Помощь:\n"
        "• «Новая» — создаёт заметку\n"
        "• «Мои заметки» — список с пагинацией\n"
        "• В просмотре: ✏️ редактировать, 🗑 удалить"
    )
    await q.edit_message_text(txt, reply_markup=main_menu())


# ---- Список и просмотр ----
async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, page_str = q.data.split("|", 1)
    page = int(page_str)
    user_id = q.from_user.id
    with SessionLocal() as s:
        total = count_notes(s, user_id=user_id)
        notes = list_notes(
            s, user_id=user_id, offset=page * PAGE_SIZE, limit=PAGE_SIZE
        )
    if total == 0:
        await q.edit_message_text("У тебя пока нет заметок.", reply_markup=main_menu())
        return
    await q.edit_message_text(
        f"Твои заметки ({total}):",
        reply_markup=notes_list_kb(notes, page, total, PAGE_SIZE),
    )


async def view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, note_id, page = q.data.split("|")
    with SessionLocal() as s:
        note = get_note(s, note_id=int(note_id), user_id=q.from_user.id)
    if not note:
        await q.edit_message_text("Заметка не найдена.", reply_markup=main_menu())
        return
    await q.edit_message_text(note.text, reply_markup=note_view_kb(note.id, int(page)))


# ---- Создание ----
async def new_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    )
    await q.edit_message_text("Отправь текст заметки одним сообщением:", reply_markup=kb)
    return AWAITING_NEW


async def new_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустую заметку не сохраняю. Введи текст.")
        return AWAITING_NEW
    with SessionLocal() as s:
        n = create_note(s, user_id=user.id, chat_id=chat_id, text=text)
    await update.message.reply_text(
        "✅ Сохранено!", reply_markup=note_view_kb(n.id, page=0)
    )
    return ConversationHandler.END


# ---- Редактирование ----
async def edit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, note_id, page = q.data.split("|")
    context.user_data["edit_note_id"] = int(note_id)
    context.user_data["edit_page"] = int(page)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    )
    await q.edit_message_text("Отправь новый текст заметки:", reply_markup=kb)
    return AWAITING_EDIT


async def edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_id = context.user_data.get("edit_note_id")
    page = context.user_data.get("edit_page", 0)
    txt = (update.message.text or "").strip()
    if not note_id or not txt:
        await update.message.reply_text("Не понял. Попробуй ещё раз.")
        return AWAITING_EDIT
    with SessionLocal() as s:
        ok = update_note(
            s, note_id=note_id, user_id=update.effective_user.id, text=txt
        )
    if not ok:
        await update.message.reply_text("Не удалось обновить заметку.", reply_markup=main_menu())
        return ConversationHandler.END
    await update.message.reply_text("✏️ Обновлено.", reply_markup=note_view_kb(note_id, page))
    return ConversationHandler.END


# ---- Удаление ----
async def del_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, note_id, page = q.data.split("|")
    with SessionLocal() as s:
        ok = delete_note(s, note_id=int(note_id), user_id=q.from_user.id)
        total = count_notes(s, user_id=q.from_user.id)
        page = max(0, min(int(page), (max(total - 1, 0)) // PAGE_SIZE))
        notes = list_notes(
            s, user_id=q.from_user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE
        )
    if not ok:
        await q.edit_message_text("Не удалось удалить.", reply_markup=main_menu())
        return
    if total == 0:
        await q.edit_message_text("Заметка удалена. Больше заметок нет.", reply_markup=main_menu())
        return
    await q.edit_message_text(
        "🗑 Удалено.", reply_markup=notes_list_kb(notes, page, total, PAGE_SIZE)
    )


# ---- Отмена ----
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text("❌ Отменено.", reply_markup=main_menu())
    elif update.message:
        await update.message.reply_text("❌ Отменено.", reply_markup=main_menu())
    return ConversationHandler.END


# ---- Конструктор приложения ----
def build_app() -> Application:
    init_db()
    token = get_settings().BOT_TOKEN
    app = Application.builder().token(token).build()

    # обычные хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(home_cb, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(list_cb, pattern=r"^list\|\d+$"))
    app.add_handler(CallbackQueryHandler(view_cb, pattern=r"^view\|\d+\|\d+$"))
    app.add_handler(CallbackQueryHandler(del_cb, pattern=r"^del\|\d+\|\d+$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))

    # диалоги
    conv_new = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_cb, pattern="^new$")],
        states={AWAITING_NEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_text)]},
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
    )
    conv_edit = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_cb, pattern=r"^edit\|\d+\|\d+$")],
        states={AWAITING_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text)]},
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
    )
    app.add_handler(conv_new)
    app.add_handler(conv_edit)

    return app

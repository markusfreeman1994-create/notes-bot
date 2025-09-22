import logging
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
from .. import messages

# ---- Константы ----
PAGE_SIZE = 5
AWAITING_NEW, AWAITING_EDIT = range(2)

# ---- Инициализация базы ----
def init_db():
    Base.metadata.create_all(bind=engine)

# ---- Глобальный обработчик ошибок ----
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # подробный стектрейс в консоль
    logging.error("Exception while handling update:", exc_info=context.error)
    # мягко уведомим пользователя (если это callback/message)
    try:
        if isinstance(update, Update):
            if update.callback_query:
                await update.callback_query.answer("⚠️ Произошла ошибка. Попробуй ещё раз.")
            elif update.message:
                await update.message.reply_text("⚠️ Что-то пошло не так. Попробуй ещё раз.")
    except Exception:
        # если даже уведомление не получилось — просто молчим
        pass

# ---- Главное меню ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Command /start from user %s", update.effective_user.id if update.effective_user else "?")
    if update.message:
        await update.message.reply_text(messages.WELCOME, reply_markup=main_menu())
    else:
        await update.callback_query.edit_message_text(messages.WELCOME, reply_markup=main_menu())

async def home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🏠 Главное меню:", reply_markup=main_menu())

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(messages.HELP, reply_markup=main_menu())

# ---- Список заметок ----
async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # извлекаем page из callback_data
    _, page_str = q.data.split("|", 1)

    # --- ВАЛИДАЦИЯ/НОРМАЛИЗАЦИЯ page ---
    try:
        page = int(page_str)
    except ValueError:
        page = 0
    if page < 0:
        page = 0
    # ------------------------------------

    user_id = q.from_user.id
    with SessionLocal() as s:
        total = count_notes(s, user_id=user_id)
        if total == 0:
            await q.edit_message_text(messages.NO_NOTES, reply_markup=main_menu())
            return

        # нормализуем page по числу страниц
        max_page = (total - 1) // PAGE_SIZE
        if page > max_page:
            page = max_page

        notes = list_notes(
            s,
            user_id=user_id,
            offset=page * PAGE_SIZE,
            limit=PAGE_SIZE,
        )

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
        await q.edit_message_text(messages.NOT_FOUND, reply_markup=main_menu())
        return
    await q.edit_message_text(note.text, reply_markup=note_view_kb(note.id, int(page)))

# ---- Создание ----
async def new_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
    await q.edit_message_text("✍️ Введи текст заметки одним сообщением:", reply_markup=kb)
    logging.info("Awaiting NEW text from user=%s", q.from_user.id)
    return AWAITING_NEW

async def new_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("⚠️ Пустую заметку не сохраняю.")
        return AWAITING_NEW
    with SessionLocal() as s:
        n = create_note(s, user_id=user.id, chat_id=chat_id, text=text)
    logging.info("Created note id=%s for user=%s", n.id, user.id)
    await update.message.reply_text(messages.SAVED, reply_markup=note_view_kb(n.id, page=0))
    return ConversationHandler.END

# ---- Редактирование ----
async def edit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, note_id, page = q.data.split("|")
    context.user_data["edit_note_id"] = int(note_id)
    context.user_data["edit_page"] = int(page)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])
    await q.edit_message_text("✏️ Введи новый текст заметки:", reply_markup=kb)
    logging.info("Awaiting EDIT text for note=%s user=%s", note_id, q.from_user.id)
    return AWAITING_EDIT

async def edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note_id = context.user_data.get("edit_note_id")
    page = context.user_data.get("edit_page", 0)
    txt = (update.message.text or "").strip()
    if not note_id or not txt:
        await update.message.reply_text("⚠️ Попробуй ещё раз.")
        return AWAITING_EDIT
    with SessionLocal() as s:
        ok = update_note(s, note_id=note_id, user_id=update.effective_user.id, text=txt)
    if not ok:
        await update.message.reply_text(messages.NOT_FOUND, reply_markup=main_menu())
        return ConversationHandler.END
    logging.info("Updated note id=%s", note_id)
    await update.message.reply_text(messages.UPDATED, reply_markup=note_view_kb(note_id, page))
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
        notes = list_notes(s, user_id=q.from_user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    if not ok:
        await q.edit_message_text(messages.NOT_FOUND, reply_markup=main_menu())
        return
    logging.info("Deleted note id=%s", note_id)
    if total == 0:
        await q.edit_message_text(messages.DELETED + "\n" + messages.NO_NOTES, reply_markup=main_menu())
        return
    await q.edit_message_text(messages.DELETED, reply_markup=notes_list_kb(notes, page, total, PAGE_SIZE))

# ---- Отмена ----
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.edit_message_text(messages.CANCELLED, reply_markup=main_menu())
    elif update.message:
        await update.message.reply_text(messages.CANCELLED, reply_markup=main_menu())
    logging.info("Action cancelled")
    return ConversationHandler.END

async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Закрываем "крутилку" у кнопки с callback_data="noop"
    await update.callback_query.answer()

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
    app.add_handler(CallbackQueryHandler(noop_cb, pattern="^noop$"))

    # диалоги
    conv_new = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_cb, pattern="^new$")],
        states={AWAITING_NEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_text)]},
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
        # per_message=False по умолчанию — норм для нашего случая
    )
    conv_edit = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_cb, pattern=r"^edit\|\d+\|\d+$")],
        states={AWAITING_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text)]},
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$")],
    )
    app.add_handler(conv_new)
    app.add_handler(conv_edit)

    # глобальный обработчик ошибок
    app.add_error_handler(error_handler)

    return app

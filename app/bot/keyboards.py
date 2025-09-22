
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    kb = [
        [InlineKeyboardButton("📝 Новая", callback_data="new")],
        [InlineKeyboardButton("📚 Мои заметки", callback_data="list|0")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(kb)

def notes_list_kb(notes, page: int, total: int, page_size: int):
    rows = []
    for n in notes:
        title = (n.text.strip().splitlines()[0] if n.text.strip() else "Без названия")[:40]
        rows.append([InlineKeyboardButton(f"📄 {title}", callback_data=f"view|{n.id}|{page}")])
    # пагинация
    max_page = (max(total - 1, 0)) // page_size
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"list|{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
    if page < max_page:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"list|{page+1}"))
    rows.append(nav or [InlineKeyboardButton("—", callback_data="noop")])
    rows.append([InlineKeyboardButton("🏠 В меню", callback_data="home")])
    return InlineKeyboardMarkup(rows)

def note_view_kb(note_id: int, page: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit|{note_id}|{page}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"del|{note_id}|{page}"),
        ],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data=f"list|{page}")],
        [InlineKeyboardButton("🏠 В меню", callback_data="home")],
    ])

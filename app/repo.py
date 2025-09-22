
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import Session
from .models import Note

def create_note(s: Session, *, user_id: int, chat_id: int, text: str) -> Note:
    n = Note(user_id=user_id, chat_id=chat_id, text=text)
    s.add(n); s.commit(); s.refresh(n)
    return n

def get_note(s: Session, *, note_id: int, user_id: int) -> Note | None:
    return s.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))

def update_note(s: Session, *, note_id: int, user_id: int, text: str) -> bool:
    res = s.execute(update(Note).where(Note.id == note_id, Note.user_id == user_id).values(text=text))
    s.commit()
    return res.rowcount > 0

def delete_note(s: Session, *, note_id: int, user_id: int) -> bool:
    res = s.execute(delete(Note).where(Note.id == note_id, Note.user_id == user_id))
    s.commit()
    return res.rowcount > 0

def count_notes(s: Session, *, user_id: int) -> int:
    return s.scalar(select(func.count()).select_from(Note).where(Note.user_id == user_id)) or 0

def list_notes(s: Session, *, user_id: int, offset: int, limit: int) -> list[Note]:
    q = select(Note).where(Note.user_id == user_id).order_by(Note.id.desc()).offset(offset).limit(limit)
    return list(s.scalars(q).all())

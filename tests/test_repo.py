# tests/test_repo.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.repo import create_note, get_note, update_note, delete_note

@pytest.fixture(scope="function")
def session():
    # Изолированная In-Memory SQLite, чтобы не трогать вашу рабочую БД
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSession()
    finally:
        Base.metadata.drop_all(bind=engine)

def test_update_respects_user_id(session):
    n = create_note(session, user_id=1, chat_id=123, text="old")
    # Чужой пользователь не должен обновить
    ok = update_note(session, note_id=n.id, user_id=2, text="hack")
    assert not ok
    # Оригинальный владелец видит старый текст
    note = get_note(session, note_id=n.id, user_id=1)
    assert note.text == "old"

def test_delete_respects_user_id(session):
    n = create_note(session, user_id=1, chat_id=123, text="to be deleted")
    # Чужой пользователь не должен удалить
    ok = delete_note(session, note_id=n.id, user_id=2)
    assert not ok
    # Запись всё ещё существует для владельца
    note = get_note(session, note_id=n.id, user_id=1)
    assert note is not None

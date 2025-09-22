# tests/conftest.py
import os, sys, pathlib

# добавить корень проекта в sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# подставим безопасные значения, чтобы импорт app.db не требовал реальный токен
os.environ.setdefault("BOT_TOKEN", "DUMMY_TOKEN")
os.environ.setdefault("DB_URL", "sqlite:///:memory:")

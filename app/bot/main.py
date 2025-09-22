import logging
from .handlers import build_app

# ВКЛЮЧАЕМ ЛОГИ: видно апдейты, ошибки и предупреждения PTB
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

def main():
    app = build_app()
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()

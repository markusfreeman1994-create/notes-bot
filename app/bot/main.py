
from .handlers import build_app

def main():
    app = build_app()
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()

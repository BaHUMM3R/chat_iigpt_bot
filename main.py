import os
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)
from groq import Groq

# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("")
GROQ_API_KEY = os.getenv("")

OWNER_ID = 5841514062  # <-- замените на свой Telegram user_id

MODEL_NAME = "llama-3.1-8b-instant"

MAX_HISTORY = 10          # сообщений в памяти
MIN_INTERVAL = 3          # секунд между сообщениями
MAX_REQUESTS = 20         # запросов
WINDOW = 600              # 10 минут

# ================== ИИ ==================

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Ты — универсальный ИИ-ассистент. "
        "Отвечай развернуто, логично и по существу. "
        "Язык по умолчанию — русский. "
        "Если вопрос технический — приводи примеры. "
        "Если вопрос неполный — уточняй. "
        "Не упоминай, что ты модель или ИИ. "
        "Не используй эмодзи. "
        "Будь вежлив и нейтрален."
    )
}

# ================== ПАМЯТЬ И ЛИМИТЫ ==================

user_memory = {}
user_limits = {}

total_users = set()
total_requests = 0

# ================== КОМАНДЫ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет!\n"
        "Я ИИ-чат-бот.\n\n"
        "Просто напиши сообщение — я отвечу.\n\n"
        "Ограничения:\n"
        "• 1 сообщение в 3 секунды\n"
        "• до 20 запросов за 10 минут\n\n"
        "Команды:\n"
        "/help — помощь\n"
        "/reset — сброс диалога"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Как пользоваться ботом:\n\n"
        "• пишите вопросы обычным текстом\n"
        "• можно вести диалог — контекст сохраняется\n"
        "• если бот просит подождать — это временно\n\n"
        "/reset — начать новый диалог"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_memory[user_id] = [SYSTEM_PROMPT]
    await update.message.reply_text("Диалог сброшен. Можно начать заново.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return

    await update.message.reply_text(
        f"Статистика:\n\n"
        f"Пользователей: {len(total_users)}\n"
        f"Запросов: {total_requests}"
    )

# ================== ОСНОВНОЙ ЧАТ ==================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_requests

    user_id = update.message.from_user.id
    text = update.message.text
    now = time.time()

    total_users.add(user_id)
    total_requests += 1

    # --- лимиты ---
    if user_id not in user_limits:
        user_limits[user_id] = []

    user_limits[user_id] = [t for t in user_limits[user_id] if now - t < WINDOW]

    if len(user_limits[user_id]) >= MAX_REQUESTS:
        await update.message.reply_text(
            "Слишком много запросов. Подождите несколько минут."
        )
        return

    if user_limits[user_id] and now - user_limits[user_id][-1] < MIN_INTERVAL:
        await update.message.reply_text(
            "Пожалуйста, не так быстро. Подождите пару секунд."
        )
        return

    user_limits[user_id].append(now)

    # --- память ---
    if user_id not in user_memory:
        user_memory[user_id] = [SYSTEM_PROMPT]

    user_memory[user_id].append({"role": "user", "content": text})
    user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=user_memory[user_id],
            timeout=15
        )

        answer = completion.choices[0].message.content

        if not answer:
            raise RuntimeError("empty response")

        user_memory[user_id].append(
            {"role": "assistant", "content": answer}
        )
        user_memory[user_id] = user_memory[user_id][-MAX_HISTORY:]

        await update.message.reply_text(answer)

    except Exception as e:
        print(f"ERROR: {e}")
        await update.message.reply_text(
            "Сервис временно недоступен. Попробуйте позже."
        )

# ================== ЗАПУСК ==================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

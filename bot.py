import os
import logging
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from binance.client import Client
import matplotlib.pyplot as plt

load_dotenv()

BASE_URL = "https://testnet.binance.vision"
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
client.API_URL = BASE_URL + "/api"

logging.basicConfig(level=logging.INFO)

user_state = {}  # { user_id: { "symbol": "BTCUSDT" } }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Binance Bot’a hoş geldin!\n"
        "Komutlar:\n"
        "/buy BTCUSDT 0.01\n"
        "/stats → Coin seçip istatistik al"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        symbol = context.args[0].upper()
        quantity = float(context.args[1])
        order = client.order_market_buy(symbol=symbol, quantity=quantity)
        await update.message.reply_text(f"✅ BUY ORDER SENT:\n{order}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{e}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        exchange_info = client.get_exchange_info()
        symbols = [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith("USDT")]

        keyboard = []
        for i in range(0, len(symbols), 3):
            row = [
                InlineKeyboardButton(text=s, callback_data=f"stats_{s}")
                for s in symbols[i:i+3]
            ]
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📌 Bir coin seç:", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{e}")

async def handle_coin_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    symbol = query.data.split("_")[1]
    user_state[query.from_user.id] = {"symbol": symbol}
    await query.message.reply_text(f"✅ `{symbol}` seçildi.\n📆 Kaç günlük istatistik istiyorsun? (örn: 7)", parse_mode="Markdown")

async def handle_day_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        if user_id not in user_state or "symbol" not in user_state[user_id]:
            return

        symbol = user_state[user_id]["symbol"]
        days = int(update.message.text)

        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_1DAY,
            limit=days
        )

        if not klines:
            await update.message.reply_text("❗ Veri bulunamadı.")
            return

        dates, opens, closes, highs, lows = [], [], [], [], []

        for k in klines:
            date = datetime.fromtimestamp(k[0] / 1000).strftime('%Y-%m-%d')
            dates.append(date)
            opens.append(float(k[1]))
            highs.append(float(k[2]))
            lows.append(float(k[3]))
            closes.append(float(k[4]))

        # Grafik
        plt.figure(figsize=(10, 6))
        plt.plot(dates, opens, label="Açılış", marker='o')
        plt.plot(dates, closes, label="Kapanış", marker='x')
        plt.plot(dates, highs, label="Max", linestyle='--', alpha=0.6)
        plt.plot(dates, lows, label="Min", linestyle='--', alpha=0.6)
        plt.title(f"{symbol} Son {days} Günlük Fiyat Grafiği")
        plt.xlabel("Tarih")
        plt.ylabel("Fiyat (USDT)")
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        image_path = "price_chart.png"
        plt.savefig(image_path)
        plt.close()

        with open(image_path, "rb") as photo:
            await update.message.reply_photo(photo=photo)

        # Durumu temizle
        del user_state[user_id]

    except Exception as e:
        await update.message.reply_text(f"❌ Error:\n{e}")

async def main():
    print(f"📦 TELEGRAM TOKEN: {TELEGRAM_BOT_TOKEN}")
    print("🚀 Bot başlatılıyor...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(handle_coin_selection, pattern="^stats_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_day_input))

    print("🤖 Bot çalışıyor, komutlar dinleniyor...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())

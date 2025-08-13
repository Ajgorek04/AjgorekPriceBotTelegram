import asyncio
import nest_asyncio
import requests
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8396501285:AAF3GY_UE65JfefAa4W0Zpn6dG5xFMdVdXo"
CHAT_ID = 6545019694

alerts = []
ALERTS_FILE = "alerts.json"

nest_asyncio.apply()

def save_alerts():
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f)

def load_alerts():
    global alerts
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            try:
                alerts = json.load(f)
            except json.JSONDecodeError:
                alerts = []

def get_price(symbol: str) -> float | None:
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        if data['retCode'] != 0 or not data['result']['list']:
            return None
        return float(data['result']['list'][0]['lastPrice'])
    except Exception:
        return None

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Użycie: /setalert <SYMBOL> <CENA> [OPIS]\n"
            "Np. /setalert BTCUSDT 30000 long pozycja"
        )
        return

    symbol = context.args[0].upper()
    try:
        price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Podaj poprawną liczbę jako cenę.")
        return

    desc = " ".join(context.args[2:]) if len(context.args) > 2 else ""

    current_price = get_price(symbol)
    if current_price is None:
        await update.message.reply_text(f"Nie znaleziono symbolu {symbol} lub błąd API.")
        return

    direction = "up" if price > current_price else "down"

    alerts.append({
        "symbol": symbol,
        "price": price,
        "desc": desc,
        "direction": direction
    })
    save_alerts()

    await update.message.reply_text(
        f"Alert ustawiony na {symbol} = {price} USD (aktualna cena: {current_price})\n"
        f"Opis: {desc}\n"
        f"Kierunek alertu: {'wzrost do' if direction=='up' else 'spadek do'} ceny"
    )

async def list_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not alerts:
        await update.message.reply_text("Brak aktywnych alertów.")
        return

    # Grupujemy alerty według symbolu
    grouped = {}
    for a in alerts:
        grouped.setdefault(a["symbol"], []).append(a)

    msg = "📊 Aktywne alerty:\n"
    for symbol, symbol_alerts in grouped.items():
        current_price = get_price(symbol)
        if current_price is None:
            current_price_str = "błąd API"
        else:
            current_price_str = f"{current_price:.4f}"

        msg += f"\n**{symbol}** (aktualna cena: {current_price_str} USD)\n"

        for a in symbol_alerts:
            opis = f" - {a['desc']}" if a['desc'] else ""
            kier = "↑" if a['direction'] == "up" else "↓"
            msg += f"  {kier} {a['price']}{opis}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def price_checker(app):
    while True:
        if alerts:
            for alert in alerts[:]:
                current = get_price(alert["symbol"])
                if current is None:
                    continue

                if alert["direction"] == "up" and current >= alert["price"]:
                    tekst_opisu = f" ({alert['desc']})" if alert['desc'] else ""
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"🚨 {alert['symbol']} osiągnął {alert['price']} USD! (Aktualnie: {current}){tekst_opisu}"
                    )
                    alerts.remove(alert)
                    save_alerts()

                elif alert["direction"] == "down" and current <= alert["price"]:
                    tekst_opisu = f" ({alert['desc']})" if alert['desc'] else ""
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"🚨 {alert['symbol']} spadł do {alert['price']} USD! (Aktualnie: {current}){tekst_opisu}"
                    )
                    alerts.remove(alert)
                    save_alerts()

        await asyncio.sleep(3)

async def main():
    load_alerts()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("listalerts", list_alerts))

    asyncio.create_task(price_checker(app))
    await app.run_polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

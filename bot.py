import time
import sqlite3

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# =========================
# SETTINGS
# =========================

TOKEN = "8034549979:AAHnXBLOdEUxL48rKsJRrKKfHFMQ7WxbmYA"
ADMIN_ID = 7593435783

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS balances(user_id INTEGER PRIMARY KEY, amount REAL)""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS investments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    profit REAL,
    start_time INTEGER,
    duration INTEGER,
    status TEXT
)
""")

conn.commit()

# =========================
# PLANS
# =========================

PLANS = {
    "Starter": [("₦3k → ₦5.2k", 3000, 5200)],
    "Premium": [("₦18k → ₦34k", 18000, 34000)],
    "VIP": [("₦108k → ₦500k", 108000, 500000)]
}

# =========================
# HELPERS
# =========================

def bal(uid):
    cursor.execute("SELECT amount FROM balances WHERE user_id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def set_bal(uid, amt):
    cursor.execute("INSERT OR IGNORE INTO balances VALUES(?,?)", (uid, 0))
    cursor.execute("UPDATE balances SET amount=? WHERE user_id=?", (amt, uid))
    conn.commit()

# =========================
# MENU
# =========================

def menu():
    return ReplyKeyboardMarkup(
        [
            ["💰 Deposit", "🏧 Withdraw"],
            ["📈 Invest", "💳 Balance"],
            ["📊 Dashboard"]
        ],
        resize_keyboard=True
    )

# =========================
# START
# =========================

async def start(update, context):
    uid = update.effective_user.id

    cursor.execute("INSERT OR IGNORE INTO users VALUES(?)", (uid,))
    cursor.execute("INSERT OR IGNORE INTO balances VALUES(?,0)", (uid,))
    conn.commit()

    await update.message.reply_text("Welcome 🚀", reply_markup=menu())

# =========================
# BUTTONS
# =========================

async def buttons(update, context):
    text = update.message.text
    uid = update.effective_user.id
    b = bal(uid)

    if text == "💰 Deposit":
        await update.message.reply_text(
            "BANK:\nPALMPAY\nNAME: WISDOM ABEL\nACC: 09138224769"
        )

    elif text == "💳 Balance":
        await update.message.reply_text(f"Balance: ₦{b}")

    elif text == "📊 Dashboard":
        cursor.execute("SELECT COUNT(*) FROM investments WHERE user_id=?", (uid,))
        inv = cursor.fetchone()[0]

        await update.message.reply_text(
            f"Balance: ₦{b}\nInvestments: {inv}"
        )

    elif text == "📈 Invest":
        kb = [
            [InlineKeyboardButton("Starter", callback_data="Starter")],
            [InlineKeyboardButton("Premium", callback_data="Premium")],
            [InlineKeyboardButton("VIP", callback_data="VIP")]
        ]
        await update.message.reply_text(
            "Choose Plan",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# =========================
# CALLBACKS
# =========================

async def cb(update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    b = bal(uid)

    if q.data in PLANS:
        kb = [
            [InlineKeyboardButton(x[0], callback_data=f"buy_{q.data}_{i}")]
            for i, x in enumerate(PLANS[q.data])
        ]
        await q.message.reply_text(
            "Plans",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data.startswith("buy_"):
        _, plan, i = q.data.split("_")
        i = int(i)

        item = PLANS[plan][i]
        amount, profit = item[1], item[2]

        if b < amount:
            await q.message.reply_text("❌ Insufficient balance")
            return

        set_bal(uid, b - amount)

        cursor.execute("""
        INSERT INTO investments(user_id, amount, profit, start_time, duration, status)
        VALUES(?,?,?,?,?,?)
        """, (uid, amount, profit, int(time.time()), 60, "active"))

        conn.commit()

        await q.message.reply_text("✅ Investment started")

# =========================
# ENGINE (SAFE LOOP)
# =========================

def engine(app):
    import asyncio

    async def loop():
        while True:
            await asyncio.sleep(30)

            now = int(time.time())

            rows = cursor.execute("""
            SELECT id, user_id, profit, start_time, duration
            FROM investments WHERE status='active'
            """).fetchall()

            for inv_id, uid, profit, start, dur in rows:
                if now >= start + dur:

                    cursor.execute(
                        "UPDATE investments SET status='done' WHERE id=?",
                        (inv_id,)
                    )
                    conn.commit()

                    set_bal(uid, bal(uid) + profit)

                    try:
                        await app.bot.send_message(uid, f"🎉 Profit received: ₦{profit}")
                    except:
                        pass

    return loop()

# =========================
# MAIN (FIXED CONNECTION SETTINGS)
# =========================

def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))
    app.add_handler(CallbackQueryHandler(cb))

    app.post_init = engine

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

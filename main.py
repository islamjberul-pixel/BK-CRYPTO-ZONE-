import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import os

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7602082599"))
FEE_PERCENT = 5
MIN_WITHDRAW = 5

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

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

# ========= KEYBOARDS =========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
        InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
        InlineKeyboardButton("📊 Balance", callback_data="balance"),
        InlineKeyboardButton("📜 History", callback_data="history")
    )
    return kb

def network_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    for net in WALLETS.keys():
        kb.insert(InlineKeyboardButton(net, callback_data=f"net_{net}"))
    return kb

def admin_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("👥 All Users", callback_data="all_users"))
    return kb

# ========= HANDLERS =========
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"Welcome {message.from_user.first_name}!", reply_markup=main_menu())

@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin Panel", reply_markup=admin_menu())

@dp.callback_query_handler(lambda c: c.data == "deposit")
async def deposit(call: types.CallbackQuery):
    await call.message.edit_text("Select Network:", reply_markup=network_menu())

@dp.callback_query_handler(lambda c: c.data.startswith("net_"))
async def show_address(call: types.CallbackQuery):
    net = call.data.split("_")[1]
    address = WALLETS[net]
    await call.message.edit_text(f"Send USDT to this {net} Address:\n\n`{address}`", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "balance")
async def balance(call: types.CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    await call.message.edit_text(f"Your Balance: {bal} USDT\nFee: {FEE_PERCENT}%", reply_markup=main_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

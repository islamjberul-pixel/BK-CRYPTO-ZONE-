import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7602082599"))
FEE_PERCENT = 5

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
conn.commit()

# ========= KEYBOARDS =========
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Deposit", callback_data="deposit"), InlineKeyboardButton(text="📤 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 Balance", callback_data="balance")]
    ])
    return kb

def network_menu():
    buttons = [[InlineKeyboardButton(text=net, callback_data=f"net_{net}")] for net in WALLETS.keys()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========= HANDLERS =========
@dp.message(F.text == "/start")
async def start(message: Message):
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"Welcome {message.from_user.first_name}!", reply_markup=main_menu())

@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin Panel: Online ✅")

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):
    await call.message.edit_text("Select Network:", reply_markup=network_menu())

@dp.callback_query(F.data.startswith("net_"))
async def show_address(call: CallbackQuery):
    net = call.data.split("_")[1]
    address = WALLETS[net]
    await call.message.edit_text(f"Send USDT to this {net} Address:\n\n`{address}`", parse_mode="Markdown")

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    await call.message.edit_text(f"Your Balance: {bal} USDT\nFee: {FEE_PERCENT}%")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

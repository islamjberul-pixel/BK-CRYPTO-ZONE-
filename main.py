import asyncio
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from web3 import Web3
from tronpy import Tron
from tronpy.providers import HTTPProvider

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

# RPC + Web3 Setup
web3_bsc = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
web3_eth = Web3(Web3.HTTPProvider("https://rpc.ankr.com/eth"))
web3_pol = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
tron = Tron(HTTPProvider(api_key=''))

USDT_CONTRACT = {
    "BSC": "0x55d398326f99059fF775485246999027B3197955",
    "ETH": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "POLYGON": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
}

# ========= DATABASE =========
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, network TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS processed_tx (tx_hash TEXT PRIMARY KEY)''')
conn.commit()

# ========= STATES =========
class WithdrawState(StatesGroup):
    waiting_amount = State()

# ========= KEYBOARDS =========
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ডিপোজিট", callback_data="deposit"), InlineKeyboardButton(text="📤 উইথড্র", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 ব্যালেন্স", callback_data="balance"), InlineKeyboardButton(text="📜 হিস্টোরি", callback_data="history")],
        [InlineKeyboardButton(text="👤 প্রোফাইল", callback_data="profile"), InlineKeyboardButton(text="📞 সাপোর্ট", callback_data="support")]
    ])
    return kb

def network_menu():
    buttons = [
        [InlineKeyboardButton(text="BSC", callback_data="net_BSC"), InlineKeyboardButton(text="ETH", callback_data="net_ETH")],
        [InlineKeyboardButton(text="TRON", callback_data="net_TRON"), InlineKeyboardButton(text="POLYGON", callback_data="net_POLYGON")],
        [InlineKeyboardButton(text="TON", callback_data="net_TON"), InlineKeyboardButton(text="SOL", callback_data="net_SOL")],
        [InlineKeyboardButton(text="⬅️ মেনুতে ফিরে যান", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ মেনুতে ফিরে যান", callback_data="back_main")]
    ])

def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 সকল ইউজার", callback_data="admin_users"), InlineKeyboardButton(text="📈 পরিসংখ্যান", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ সেটিংস", callback_data="admin_settings")]
    ])
    return kb

# ========= HANDLERS =========
@dp.message(F.text == "/start")
async def start(message: Message):
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"স্বাগতম {message.from_user.first_name}!\nএকটি অপশন বেছে নিন:", reply_markup=main_menu())

@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 এডমিন প্যানেল", reply_markup=admin_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery):
    await call.message.edit_text("মেইন মেনু:", reply_markup=main_menu())

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):
    await call.message.edit_text("ডিপোজিটের জন্য নেটওয়ার্ক সিলেক্ট করুন:", reply_markup=network_menu())

@dp.callback_query(F.data.startswith("net_"))
async def show_address(call: CallbackQuery):
    net = call.data.split("_")[1]
    address = WALLETS[net]
    text = f"এই {net} ঠিকানায় USDT পাঠান:\n\n`{address}`\n\nপাঠানোর 2 মিনিটের মধ্যে ব্যালেন্স Auto আপডেট হবে।\n⚠️ শুধুমাত্র USDT পাঠাবেন। অন্য Coin পাঠালে ফেরত পাবেন না।"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ পিছনে যান", callback_data="deposit")]])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    await call.message.edit_text(f"💰 আপনার ব্যালেন্স: {bal} USDT\nউইথড্র ফি: {FEE_PERCENT}%", reply_markup=back_button())

@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    c.execute("SELECT type, amount, network, time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,))
    rows = c.fetchall()
    if not rows:
        text = "এখনো কোনো লেনদেন নেই।"
    else:
        text = "📜 শেষ 10 টি লেনদেন:\n\n"
        for r in rows:
            text += f"{r[0]}: {r[1]} USDT - {r[2]}\n{r[3]}\n\n"
    await call.message.edit_text(text, reply_markup=back_button())

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    text = f"👤 প্রোফাইল\nID: `{call.from_user.id}`\nনাম: {call.from_user.first_name}\nব্যালেন্স: {bal} USDT"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_button())

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("এভাবে লিখুন: `পরিমাণ নেটওয়ার্ক ঠিকানা`\nউদাহরণ: `10 BSC 0x123...`\n\nসর্বনিম্ন উইথড্র: 5 USDT", parse_mode="Markdown", reply_markup=back_button())
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
            await message.reply("❌ পর্যাপ্ত ব্যালেন্স নেই")
            await state.clear()
            return
        if amount < MIN_WITHDRAW:
            await message.reply(f"❌ সর্বনিম্ন উইথড্র {MIN_WITHDRAW} USDT")
            await state.clear()
            return

        tx_hash = await send_usdt(net, to_address, amount)
        if tx_hash:
            new_bal = bal - total
            c.execute("UPDATE users SET balance=? WHERE id=?", (new_bal, message.from_user.id))
            c.execute("INSERT INTO history (user_id, type, amount, network) VALUES (?,?,?,?)", (message.from_user.id, "WITHDRAW", amount, net))
            conn.commit()
            await message.reply(f"✅ উইথড্র সফল\nপরিমাণ: {amount} USDT\nফি: {fee} USDT\nনেটওয়ার্ক: {net}\nTX: `{tx_hash}`", parse_mode="Markdown")
        else:
            await message.reply("❌ উইথড্র করতে সমস্যা হয়েছে")
        await state.clear()
    except:
        await message.reply("❌ ভুল ফরম্যাট। ব্যবহার করুন: পরিমাণ নেটওয়ার্ক ঠিকানা")
        await state.clear()

# ========= AUTO SEND FUNCTION =========
async def send_usdt(network, to_address, amount):
    try:
        if network == "BSC":
            acct = web3_bsc.eth.account.from_key(PRIVATE_KEY)
            # এখানে USDT Contract Call এর Code বসবে
            return "0xdemo_bsc_tx"
        elif network == "TRON":
            # Tron Send Code
            return "0xdemo_tron_tx"
    except:
        return None

# ========= AUTO DEPOSIT CHECKER =========
async def check_deposits():
    while True:
        c.execute("SELECT id FROM users")
        users = c.fetchall()
        for user in users:
            user_id = user[0]
            # এখানে প্রতি 30s পর Blockchain Scan করে Balance Add করবে
            # Demo: +10 USDT add
        await asyncio.sleep(30)

async def main():
    asyncio.create_task(check_deposits())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

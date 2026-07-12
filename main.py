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
from web3.contract import Contract
from tronpy import Tron
from tronpy.providers import HTTPProvider

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7602082599"))
FEE_PERCENT = 5
MIN_WITHDRAW = 5
CHECK_INTERVAL = 30 # 30 সেকেন্ড পর Scan

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Wallet Addresses
WALLETS = {
    "BSC": "0xdcdB5EB1C3621Af39E6580e318dAC4615ae28989",
    "ETH": "0x417ae2bbd0639b46e562fd4056526551ed1cba7359470f5c057c1ca792808081",
    "TRON": "TCPeHUB1cMrVoa3vHY3VnVzHbzSys93sHB",
    "POLYGON": "CV5sr76H7GHi6jTvHpQaapFjzW7sBop9YaQQKGE3oDTf",
}

NETWORK_NAMES = {
    "BSC": "USDT.BEP20",
    "ETH": "USDT.ERC20",
    "TRON": "USDT.TRC20",
    "POLYGON": "USDT.POLYGON",
}

# RPC + Web3 Setup
web3_bsc = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
web3_eth = Web3(Web3.HTTPProvider("https://rpc.ankr.com/eth"))
web3_pol = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
tron = Tron(HTTPProvider(api_key=''))

# USDT Contract ABI - শুধু balanceOf আর transfer লাগবে
ERC20_ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]

USDT_CONTRACT = {
    "BSC": web3_bsc.eth.contract(address=Web3.to_checksum_address("0x55d398326f99059fF775485246999027B3197955"), abi=ERC20_ABI),
    "ETH": web3_eth.eth.contract(address=Web3.to_checksum_address("0xdAC17F958D2ee523a2206206994597C13D831ec7"), abi=ERC20_ABI),
    "POLYGON": web3_pol.eth.contract(address=Web3.to_checksum_address("0xc2132D05D31c914a87C6611C10748AEb04B58e8F"), abi=ERC20_ABI)
}

TRON_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t" # TRC20 USDT

# ========= DATABASE =========
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, network TEXT, tx_hash TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS processed_tx (tx_hash TEXT PRIMARY KEY)''')
conn.commit()

# ========= STATES =========
class WithdrawState(StatesGroup):
    waiting_amount = State()
    waiting_address = State()

user_withdraw_data = {}

# ========= KEYBOARDS =========
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ডিপোজিট", callback_data="deposit"), InlineKeyboardButton(text="📤 উইথড্র", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 ব্যালেন্স", callback_data="balance"), InlineKeyboardButton(text="📜 হিস্টোরি", callback_data="history")],
        [InlineKeyboardButton(text="👤 প্রোফাইল", callback_data="profile")]
    ])

def network_menu():
    buttons = [[InlineKeyboardButton(text=f"{net} - {NETWORK_NAMES[net]}", callback_data=f"net_{net}")] for net in WALLETS.keys()]
    buttons.append([InlineKeyboardButton(text="⬅️ মেনুতে ফিরে যান", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def withdraw_network_menu(user_id):
    c.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    bal = c.fetchone()[0]
    buttons = [[InlineKeyboardButton(text=f"{net} - ব্যালেন্স: {bal} USDT", callback_data=f"wd_net_{net}")] for net in WALLETS.keys()]
    buttons.append([InlineKeyboardButton(text="⬅️ মেনুতে ফিরে যান", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ মেনুতে ফিরে যান", callback_data="back_main")]])

# ========= HANDLERS =========
@dp.message(F.text == "/start")
async def start(message: Message):
    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    await message.answer(f"স্বাগতম {message.from_user.first_name}!\nএকটি অপশন বেছে নিন:", reply_markup=main_menu())

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
    net_name = NETWORK_NAMES[net]
    text = f"এই {net_name} ঠিকানায় USDT পাঠান:\n\n`{address}`\n\nপাঠানোর 2 মিনিটের মধ্যে ব্যালেন্স Auto আপডেট হবে।\n⚠️ শুধুমাত্র {net_name} নেটওয়ার্কের USDT পাঠাবেন।"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=back_button())

@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    c.execute("SELECT balance FROM users WHERE id=?", (call.from_user.id,))
    bal = c.fetchone()[0]
    await call.message.edit_text(f"💰 আপনার ব্যালেন্স: {bal} USDT\nউইথড্র ফি: {FEE_PERCENT}%", reply_markup=back_button())

@dp.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await call.message.edit_text("কোন নেটওয়ার্ক থেকে উইথড্র করবেন সিলেক্ট করুন:", reply_markup=withdraw_network_menu(call.from_user.id))

@dp.callback_query(F.data.startswith("wd_net_"))
async def withdraw_amount(call: CallbackQuery, state: FSMContext):
    net = call.data.split("_")[2]
    user_withdraw_data[call.from_user.id] = {"net": net}
    await call.message.edit_text(f"আপনি {net} সিলেক্ট করেছেন\nকত USDT উইথড্র করবেন লিখুন:\nসর্বনিম্ন: {MIN_WITHDRAW} USDT", reply_markup=back_button())
    await state.set_state(WithdrawState.waiting_amount)

@dp.message(WithdrawState.waiting_amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < MIN_WITHDRAW: return await message.reply(f"❌ সর্বনিম্ন উইথড্র {MIN_WITHDRAW} USDT")
        user_withdraw_data[message.from_user.id]["amount"] = amount
        await message.answer("এখন যে ঠিকানায় টাকা পাঠাবেন সেটি দিন:", reply_markup=back_button())
        await state.set_state(WithdrawState.waiting_address)
    except:
        await message.reply("❌ সঠিক সংখ্যা দিন")

@dp.message(WithdrawState.waiting_address)
async def process_withdraw(message: Message, state: FSMContext):
    to_address = message.text
    data = user_withdraw_data.get(message.from_user.id)
    net, amount = data["net"], data["amount"]

    c.execute("SELECT balance FROM users WHERE id=?", (message.from_user.id,))
    bal = c.fetchone()[0]
    fee = round(amount * FEE_PERCENT / 100, 2)
    total = amount + fee

    if total > bal:
        await message.reply("❌ পর্যাপ্ত ব্যালেন্স নেই")
        return await state.clear()

    await message.answer("⏳ উইথড্র প্রসেস হচ্ছে...")
    tx_hash = await send_usdt(net, to_address, amount)

    if tx_hash:
        new_bal = bal - total
        c.execute("UPDATE users SET balance=? WHERE id=?", (new_bal, message.from_user.id))
        c.execute("INSERT INTO history (user_id, type, amount, network, tx_hash) VALUES (?,?,?,?,?)", (message.from_user.id, "WITHDRAW", amount, net, tx_hash))
        conn.commit()
        await message.reply(f"✅ উইথড্র সফল\nনেটওয়ার্ক: {net}\nপরিমাণ: {amount} USDT\nফি: {fee} USDT\nTX: `{tx_hash}`", parse_mode="Markdown")
    else:
        await message.reply("❌ উইথড্র করতে সমস্যা হয়েছে। Gas Fee আছে কিনা চেক করুন")
    await state.clear()

# ========= AUTO SEND =========
async def send_usdt(network, to_address, amount):
    try:
        acct = web3_bsc.eth.account.from_key(PRIVATE_KEY) if network!= "TRON" else None
        amount_wei = int(amount * 10**6) # USDT has 6 decimals on TRON, 18 on EVM

        if network == "BSC":
            contract = USDT_CONTRACT["BSC"]
            nonce = web3_bsc.eth.get_transaction_count(acct.address)
            txn = contract.functions.transfer(Web3.to_checksum_address(to_address), amount_wei).build_transaction({'from': acct.address, 'nonce': nonce, 'gas': 100000, 'gasPrice': web3_bsc.to_wei('5', 'gwei')})
            signed = web3_bsc.eth.account.sign_transaction(txn, PRIVATE_KEY)
            tx_hash = web3_bsc.eth.send_raw_transaction(signed.rawTransaction)
            return web3_bsc.to_hex(tx_hash)

        elif network == "TRON":
            txn = await tron.trx.transfer(WALLETS["TRON"], to_address, amount_wei).build().sign(PRIVATE_KEY).broadcast()
            return txn['txID']

    except Exception as e:
        print(f"Withdraw Error: {e}")
        return None

# ========= AUTO DEPOSIT =========
async def check_balance(network, address):
    if network == "BSC":
        return USDT_CONTRACT["BSC"].functions.balanceOf(Web3.to_checksum_address(address)).call() / 10**18
    elif network == "TRON":
        contract = tron.get_contract(TRON_USDT)
        return contract.functions.balanceOf(address) / 10**6
    return 0

async def check_deposits():
    last_balances = {}
    while True:
        try:
            for net, address in WALLETS.items():
                current_bal = await check_balance(net, address)
                if net not in last_balances: last_balances[net] = current_bal

                if current_bal > last_balances[net]:
                    diff = current_bal - last_balances[net]
                    c.execute("UPDATE users SET balance = balance +? WHERE id =?", (diff, ADMIN_ID)) # Demo: Admin এ Add হবে
                    c.execute("INSERT INTO history (user_id, type, amount, network) VALUES (?,?,?,?)", (ADMIN_ID, "DEPOSIT", diff, net))
                    conn.commit()
                    await bot.send_message(ADMIN_ID, f"✅ নতুন ডিপোজিট\nনেটওয়ার্ক: {net}\nপরিমাণ: {diff} USDT")
                    last_balances[net] = current_bal
        except Exception as e:
            print(f"Deposit Check Error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    asyncio.create_task(check_deposits())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

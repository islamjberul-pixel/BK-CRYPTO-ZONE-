import os
import qrcode
import asyncio
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from web3 import Web3
from tronpy import Tron
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7602082599 # তোমার ID
ADMIN_WALLET = os.getenv("ADMIN_WALLET") # Fee জমানোর Wallet
ADMIN_PRIVATE_KEY = os.getenv("ADMIN_PRIVATE_KEY") # Fee জমানোর Private Key

WITHDRAW_FEE = 5.0 # %
SWAP_FEE = 1.5 # %
MIN_WITHDRAW = 5.0 # USDT

# Network RPC
BSC_RPC = "https://bsc-dataseed.binance.org/"
w3_bsc = Web3(Web3.HTTPProvider(BSC_RPC))
TRON = Tron()

# Simple Database - Railway এ পরে SQLite লাগাবো
user_data = {}
user_temp = {}

# Top 15 Token
TOKENS = {
    "USDT": {"BEP20": "0x55d398326f99059fF775485246999027B3197955", "TRC20": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", "ERC20": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
    "USDC": {"BEP20": "0x8AC76a51cc950d9822D68b83fE772Adbb903b995", "ERC20": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    "BNB": {"BEP20": "NATIVE"},
    "ETH": {"ERC20": "NATIVE"},
    "TRX": {"TRC20": "NATIVE"},
    "BTC": {}, "SOL": {}, "TON": {}, "XRP": {}, "DOGE": {}, "PEPE": {}, "WIF": {}, "ARB": {}, "OP": {}, "NOT": {}
}

# ========== KEYBOARD ==========
def main_menu():
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("📥 Deposit", callback_data="deposit"), InlineKeyboardButton("📤 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🔄 Swap", callback_data="swap"), InlineKeyboardButton("📜 History", callback_data="history")],
        [InlineKeyboardButton("👤 Account", callback_data="account"), InlineKeyboardButton("📊 Crypto Rate", callback_data="rate")],
        [InlineKeyboardButton("🎧 Support", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu"), InlineKeyboardButton("⬇️ Menu", callback_data="menu")]])

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"balances": {"USDT": 0.0, "BNB": 0.0}, "addresses": {}}
    await update.message.reply_text(f"Welcome to Gem Wallet Bot ✅\n\nTotal Balance: $0.00", reply_markup=main_menu())

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID:
        await update.message.reply_text("Access Denied")
        return
    keyboard = [
        [InlineKeyboardButton("📊 All History", callback_data="admin_history")],
        [InlineKeyboardButton("💵 Income Report", callback_data="admin_income")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("💸 Withdraw Profit", callback_data="admin_withdraw_profit")]
    ]
    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== BUTTON HANDLER ==========
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu":
        await query.edit_message_text("Main Menu", reply_markup=main_menu())

    elif data == "balance":
        text = "💰 Your Balance\n\n"
        total = 0
        for token, bal in user_data[user_id]["balances"].items():
            text += f"{token}: {bal}\n"
            total += bal
        text += f"\nTotal: ${total}"
        await query.edit_message_text(text, reply_markup=back_menu())

    elif data == "deposit":
        keyboard = [[InlineKeyboardButton(t, callback_data=f"dep_token_{t}")] for t in list(TOKENS.keys())[:15]]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
        await query.edit_message_text("কোন Token Deposit করবা?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("dep_token_"):
        token = data.split("_")[2]
        keyboard = [[InlineKeyboardButton(n, callback_data=f"dep_net_{token}_{n}")] for n in TOKENS[token].keys()]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="deposit")])
        await query.edit_message_text(f"{token} এর কোন Network?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("dep_net_"):
        _,_,token,net = data.split("_")
        address = "0xDemoBEP20Address123" if "BEP" in net or "ERC" in net else "TDemoTRC20Address123"
        user_data[user_id]["addresses"][f"{token}_{net}"] = address
        qr = qrcode.make(address)
        bio = BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)
        await context.bot.send_photo(chat_id=user_id, photo=bio, caption=f"তোমার {token} {net} Address:\n`{address}`\n\n⚠️ শুধু {net} Network এ পাঠাবা", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "withdraw":
        keyboard = [[InlineKeyboardButton(t, callback_data=f"with_token_{t}")] for t,b in user_data[user_id]["balances"].items() if b > 0]
        if not keyboard: keyboard = [[InlineKeyboardButton("Balance নেই", callback_data="none")]]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
        await query.edit_message_text("কোন Token Withdraw করবা?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("with_token_"):
        token = data.split("_")[2]
        await query.edit_message_text(f"কত {token} Withdraw করবা?\nMinimum: {MIN_WITHDRAW}\nFee: {WITHDRAW_FEE}%", reply_markup=back_menu())
        user_temp[user_id] = {"action": "withdraw_amount", "token": token}

    elif data == "admin_income":
        await query.edit_message_text("মোট Withdraw Fee Income: 0 USDT\nমোট Swap Fee Income: 0 USDT\nমোট লাভ: 0 USDT", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]))

    elif data == "admin_withdraw_profit":
        await query.edit_message_text("কত USDT তুলবা? Address সহ লিখো\nExample: 100 0xYourAddress", reply_markup=back_menu())
        user_temp[user_id] = {"action": "admin_withdraw"}

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in user_temp:
        if user_temp[user_id]["action"] == "withdraw_amount":
            try:
                amount = float(text)
                token = user_temp[user_id]["token"]
                fee = amount * (WITHDRAW_FEE/100)
                receive = amount - fee
                await update.message.reply_text(f"Address দিন:\n⚠️ একই Network এর Address দিবেন। ভুল দিলে টাকা যাবে না। এর জন্য Admin দায়ী না।")
                user_temp[user_id]["amount"] = amount
                user_temp[user_id]["receive"] = receive
                user_temp[user_id]["action"] = "withdraw_address"
            except:
                await update.message.reply_text("সঠিক Amount দিন")

        elif user_temp[user_id]["action"] == "withdraw_address":
            address = text
            # এখানে Auto Send Logic আসবে
            await update.message.reply_text(f"Withdraw Request Success! {user_temp[user_id]['receive']} {user_temp[user_id]['token']} পাঠানো হচ্ছে...", reply_markup=main_menu())
            del user_temp[user_id]

# ========== RUN BOT ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("Bot Running on Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()

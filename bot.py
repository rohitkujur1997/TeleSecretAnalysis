import os, re, mimetypes, json, requests, asyncio, pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telethon.errors.rpcerrorlist import PhoneNumberInvalidError
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChannel, MessageMediaDocument, MessageMediaPhoto, Document
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from io import BytesIO
import logging
logging.basicConfig(level=logging.INFO)
task_queue = asyncio.Queue()

# Your Telegram API credentials
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def analysis(update:Update,context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id 
    link= context.args[0]
    ticker = link+".NS"
    current_year = datetime.today().year

    # Month order for x-axis
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Dictionary to hold year-wise data
    yearly_data = {}

    # Loop through last 10 years (including current year)
    for year in range(current_year - 5 + 1, current_year + 1):
        start = f"{year}-01-01"
        end = datetime.today().strftime('%Y-%m-%d') if year == current_year else f"{year}-12-31"
        
        # Download monthly data
        df = yf.download(ticker, start=start, end=end, interval='1mo', progress=False)
        if df.empty:
            continue  # Skip if no data
        
        # Add Month column and align order
        df['Month'] = df.index.strftime('%b')
        df['Month'] = pd.Categorical(df['Month'], categories=months, ordered=True)
        df.sort_values('Month', inplace=True)
        
        # Store close prices with month index
        yearly_data[year] = df[['Month', 'Close']]

    # Plotting
    plt.figure(figsize=(14, 7))

    for year, df in yearly_data.items():
        plt.plot(df['Month'], df['Close'], marker='o', label=str(year))

    plt.title(f"{ticker} - Monthly Close Price (Past 5 Years: {current_year-5} to {current_year})")
    plt.xlabel("Month")
    plt.ylabel("Price (INR)")
    plt.grid(True)
    plt.legend(title="Year", loc='upper left', bbox_to_anchor=(1, 1))
    plt.tight_layout()

    # Save chart image
    plt.savefig("monthly_comparison_last_10_years.png")
    filename="monthly_comparison_last_10_years.png"
    with open(filename, 'rb') as f:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
    os.remove(filename)  # Clean up=
    

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id        
        user_id = update.effective_user.id
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        await update.message.reply_text(text=f"🙌Welcome to the TeleSecretDownloader Bot!\n"
                                        f"Here after login you can dowload files from PRIVATE Channel or Groups which does'nt allow downloading.🚀\n"
                                        f"📢Devs Group:@\n\n"
                                        f"💼Account: `{user_id}`\n"
                                        f"Type /payment to buy🎟(1🎟=1Photo🖼 or Video🎞 or File📁)\n"
                                        f"✈Type /invite to earn 🎟 by inviting friends.\n\n"
                                        f"🆘Use /help to see all available commands.\n\n"
                                        f"‼Privacy guranteed: We don't share your session or file your download.\n"
                                        f"🔗Referral Link: `https//t.me/{context.bot.username}?start={user_id}`",
                                        parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Session error: {e}")
        await client.disconnect()
        return


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id

        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        await analysis(update,context)
        await context.bot.send_message(chat_id=chat_id,text=f"⚠️ Error: {link}")
        
        """ #await update.message.reply_text(f"🔍 Searching in `{channel_id}`... Please wait.", parse_mode="Markdown")
        await update.message.reply_text(f"🔍 Searching... Please wait.", parse_mode="Markdown")

        peer = PeerChannel(channel_id)
        message = await client.get_messages(peer, ids=message_id)
        #await update.message.reply_text(str(message))

        await update.message.reply_text(f"🖼️ Photo Media Found")
        # Add download button
        button = InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Download", callback_data=f"download:{channel_id}:{message_id}:{False}")]])
        await update.message.reply_text("Click below to download this photo:", reply_markup=button)
        #await update.message.reply_text(f"- Message ID: {message.id}") """

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")
        await client.disconnect()





async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Nsadsdddsasadsadad")



# This function is triggered when button is clicked
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    """ if query.data == "dailyclaim":
        await dailyclaim(update,context) """

async def setup(application):
    # Set commands
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help"),
        BotCommand("profile", "View your profile"),
        BotCommand("post", "<File Link> \nDownload one post"),
        BotCommand("invite", "Invite and earn"),
        BotCommand("dailyclaim", "Claim today's claim"),
        BotCommand("logout", "Delete Session")
    ])
    # Set menu button to show commands
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# Bot entry point
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    """ app.add_handler(CommandHandler("profile", profile))  """
    app.add_handler(CommandHandler("post", post)) 
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.post_init = setup
    app.run_polling()

if __name__ == '__main__':
    logging.info("Bot is starting...")
    # Start the event loop using asyncio.run(main())
    asyncio.run(main())
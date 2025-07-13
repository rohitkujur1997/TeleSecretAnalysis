import os, asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime
import logging
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import math
logging.basicConfig(level=logging.INFO)
task_queue = asyncio.Queue()

# Your Telegram API credentials
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

def download_monthly_data(ticker, start_year, end_year):
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    yearly_data = {}

    for year in range(start_year, end_year + 1):
        start = f"{year}-01-01"
        end = datetime.today().strftime('%Y-%m-%d') if year == end_year else f"{year}-12-31"

        df = yf.download(ticker, start=start, end=end, interval='1mo', progress=False)
        if df.empty:
            continue

        df['Month'] = df.index.strftime('%b')
        df['Month'] = pd.Categorical(df['Month'], categories=months, ordered=True)
        df.sort_values('Month', inplace=True)

        yearly_data[year] = df[['Month', 'Close']]

    return yearly_data


async def plot_yearly_grid(yearly_data, ticker,update:Update,context:ContextTypes.DEFAULT_TYPE):
    num_years = len(yearly_data)
    cols = 3
    rows = math.ceil(num_years / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
    axes = axes.flatten()

    for idx, (year, df) in enumerate(yearly_data.items()):
        ax = axes[idx]
        ax.plot(df['Month'], df['Close'], marker='o', label=str(year))

        min_idx = df['Close'].idxmin()
        max_idx = df['Close'].idxmax()
        min_monthw = df.loc[min_idx, 'Month']
        max_monthw = df.loc[max_idx, 'Month']
        if isinstance(min_monthw, pd.Series):
            min_monthw = min_monthw.values[0]
        if isinstance(max_monthw, pd.Series):
            max_monthw = max_monthw.values[0]

        min_price = df.loc[min_idx, 'Close'].squeeze()
        max_price = df.loc[max_idx, 'Close'].squeeze()

        percent_change = ((max_price - min_price) / min_price) * 100

        print(f"{year}: {min_monthw}-{max_monthw} | % Change: {percent_change:.2f}%")

        min_month = df.loc[min_idx, 'Month'].item()
        max_month = df.loc[max_idx, 'Month'].item()

        ax.axvline(x=min_month, linestyle='solid', color='red', alpha=0.3)
        ax.axvline(x=max_month, linestyle='solid', color='green', alpha=0.3)

        # ⬇️ Add percent change as text box
        ax.text(0.05, 0.95, f"% Change:\n{percent_change:.2f}%", transform=ax.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.5))

        ax.set_title(f"{ticker} - {year}")
        ax.set_xlabel("Month")
        ax.set_ylabel("Price (INR)")
        ax.grid(True)

    for i in range(len(yearly_data), len(axes)):
        fig.delaxes(axes[i])

    plt.tight_layout()
    filename = f"{ticker}_years_charts.png"
    plt.savefig(filename, dpi=300, format='png')
    logging.info("Saved image:", filename, "Size:", os.path.getsize(filename))
    with open(filename, 'rb') as f:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
    os.remove(filename)  # CleanUp


async def analysis(update:Update,context:ContextTypes.DEFAULT_TYPE):
    ticker = context.args[0]+".NS"
    current_year = datetime.today().year
    start_year = 1995

    yearly_data = download_monthly_data(ticker, start_year, current_year)
    await plot_yearly_grid(yearly_data, ticker,update,context)

async def analysi(update:Update,context: ContextTypes.DEFAULT_TYPE):
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
    for year in range(current_year - 20 + 1, current_year + 1):
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

    plt.title(f"{ticker} - Monthly Close Price (Past Years: From listing to {current_year})")
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
    os.remove(filename)  # CleanUp
    

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id        
        user_id = update.effective_user.id
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        await update.message.reply_text(text=f"🙌Welcome to the TeleSecretAnalysis Bot!\n"
                                        f"Here you can analyze any listed indian stock.🚀\n"
                                        f"📢Devs Group:@\n\n"
                                        f"💼Account: `{user_id}`\n"
                                        f"Type /analyze <Stock Name>\n"
                                        f"🆘Use /help to see all available commands.\n\n"
                                        f"🔗Invite Link: `https//t.me/{context.bot.username}?start={user_id}`",
                                        parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Session error: {e}")
        await client.disconnect()
        return


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id

        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        await analysis(update,context)
        await context.bot.send_message(chat_id=chat_id,text=f"Analysis Done.")

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
        BotCommand("analyze", "<Stock Name> \nGet charts")
    ])
    # Set menu button to show commands
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# Bot entry point
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("analyze", analyze)) 
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.post_init = setup
    app.run_polling()

if __name__ == '__main__':
    logging.info("Bot is starting...")
    # Start the event loop using asyncio.run(main())
    asyncio.run(main())
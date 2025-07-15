import os, asyncio, pytz
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime
import logging
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
import math, csv, json
import firebase_admin
from firebase_admin import credentials, firestore
logging.basicConfig(level=logging.INFO)
task_queue = asyncio.Queue()

# Your Telegram API credentials
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Load credentials from environment variable
firebase_json = os.getenv("FIREBASE_CREDENTIALS")
if not firebase_json:
    raise ValueError("❌ FIREBASE_CREDENTIALS environment variable is not set or is empty.")
cred_dict = json.loads(firebase_json)

# Store Firebase app globally (so it initializes once)
firebase_app = None
db = None


def init_firebase():
    global firebase_app, db
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(cred)
        db = firestore.client()

def set_user_payment(user_id):
    #init_firebase()
    now = datetime.now(pytz.UTC)
    today_str = now.strftime("%Y-%m-%d")
    db.collection("TeleSecretAnalysys").document(str(user_id)).set({
        "Membership": "Active",
        "FNO": True,
        "Average%": 20,
        "start_date": today_str
    })

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
    msg=""

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

        msg+=f"{year}: {min_monthw}-{max_monthw} | % Change: {percent_change:.2f}%\n"

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
    logging.info(f"Saved image: {filename}, Size: {os.path.getsize(filename)} bytes")

    # Send as media group
    with open(filename, 'rb') as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    # Optional message
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    # Clean up
    os.remove(filename)


async def analysis(update:Update,context:ContextTypes.DEFAULT_TYPE):
    ticker = context.args[0]+".NS"
    current_year = datetime.today().year
    start_year = 1995

    yearly_data = download_monthly_data(ticker, start_year, current_year)
    await plot_yearly_grid(yearly_data, ticker,update,context)

def get_nearest_close(date, df):
    while date not in df.index and date >= df.index.min():
        date -= timedelta(days=1)
    return df.loc[date]['Close'] if date in df.index else None

async def suggestion(ticker_symbols,update:Update,context:ContextTypes.DEFAULT_TYPE):
    start_day, start_month = 10, 5
    end_day, end_month = 30, 6
    years_back = 10

    end_date = datetime.today()
    start_date = end_date.replace(year=end_date.year - years_back)
    # Store all results for plotting
    all_results = {}

    for ticker_symbol in ticker_symbols:
        try:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval="1d")
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df[['Close']]

            results = []
            for year in range(end_date.year - 1, end_date.year - years_back - 1, -1):
                try:
                    d1 = datetime(year, start_month, start_day)
                    d2 = datetime(year, end_month, end_day)
                    close1 = get_nearest_close(d1, df)
                    close2 = get_nearest_close(d2, df)
                    if close1 and close2:
                        pct = ((close2 - close1) / close1) * 100
                        results.append({
                            "Year": year,
                            "% Change": round(pct, 2)
                        })
                except Exception as e:
                    await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Skipped {ticker_symbol} {year} due to error: {e}")
                    continue

            all_results[ticker_symbol] = pd.DataFrame(results).sort_values('Year')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Skipped {ticker_symbol} {year} due to error: {e}")
            continue

    """ # Merge all results into a single DataFrame
    combined_df = pd.DataFrame({'Year': sorted([r['Year'] for r in results])})
    for symbol in ticker_symbols:
        df_temp = all_results[symbol]
        combined_df[symbol] = df_temp['% Change'].values
    
    await send_long_message(context, update.effective_chat.id,combined_df.to_string(index=False)) """

    # Plot grouped bar chart
    # Define grid size dynamically
    num_tickers = len(ticker_symbols)
    cols = 2  # You can increase for wider layouts
    rows = math.ceil(num_tickers / cols)

    # Create subplots grid
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
    axes = axes.flatten()  # Flatten for easy indexing

    # Plot each ticker in its subplot
    for i, symbol in enumerate(ticker_symbols):
        ax = axes[i]
        df_temp = all_results[symbol]
        years = df_temp['Year'].astype(str)
        changes = df_temp['% Change']
        colors = ['green' if val > 0 else 'red' for val in changes]

        bars = ax.bar(years, changes, color=colors)
        
        # Annotate bars
        for bar, value in zip(bars, changes):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height,
                    f"{value:.2f}%", ha='center', va='bottom' if height > 0 else 'top', fontsize=8)

        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_title(symbol)
        ax.set_xlabel("Year")
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        if i % cols == 0:
            ax.set_ylabel("% Change")

    # Remove unused axes (if any)
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    # Final layout adjustments
    fig.suptitle(f"% Change from {start_day}/{start_month} to {end_day}/{end_month} (Last {years_back} Years)", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(str(update.effective_chat.id)+"suggestion.png", dpi=300)
    suggestionimg=str(update.effective_chat.id)+"suggestion.png"
    logging.info(f"Saved image: {suggestionimg}, Size: {os.path.getsize(suggestionimg)} bytes")

    # Send as media group
    with open(suggestionimg, 'rb') as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)
    #plt.show()
    
    # Clean up
    os.remove(suggestionimg)

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id        
        user_id = update.effective_user.id
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        init_firebase()
        doc = db.collection("TeleSecretAnalysis").document(str(user_id)).get()
        if not doc.exists:
            set_user_payment(user_id)
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        FNO = data.get("FNO", False)
        Membership = data.get("Membership", "")
        Avg = data.get("Average%", 0)

        await update.message.reply_text(text=f"🙌Welcome to the TeleSecretAnalysis Bot!\n"
                                        f"Here you can analyze any listed indian stock.🚀\n"
                                        f"📢Devs Group:@\n\n"
                                        f"💼Account: `{user_id}`\n"
                                        f"FNO:{FNO}, Membership:{Membership}, Average%:{Avg}"
                                        f"Type /analyze <Stock Name>\n"
                                        f"Type /suggest\n"
                                        f"🆘Use /help to see all available commands.\n\n"
                                        f"🔗Invite Link: `https//t.me/{context.bot.username}?start={user_id}`",
                                        parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Session error: {e}")
        await client.disconnect()
        return

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        await client.connect()
        if context.args and context.args[0]:
            ticker_symbols = [context.args[0]+".NS"]
            await context.bot.send_message(chat_id=chat_id,text=ticker_symbols)
        else:
            values = []
            init_firebase()
            data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
            FNO = data.get("FNO", False)
            
            await context.bot.send_message(chat_id=chat_id,text=FNO)
            """ # Open the CSV file
            with open("output_data.csv", newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header (row 1)

                for row in reader:
                    if len(row) > 0 and row[0]:  # Check if column A has value
                        values.append(row[0])
            ticker_symbols = [item + ".NS" for item in values]
        await suggestion(ticker_symbols,update,context)
        await context.bot.send_message(chat_id=chat_id,text=f"Suggestion Done.") """

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")
        await client.disconnect()

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

async def send_long_message(client, entity, message, chunk_size=4096):
    for i in range(0, len(message), chunk_size):
        await client.send_message(entity, message[i:i+chunk_size])

async def setup(application):
    # Set commands
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help"),
        BotCommand("analyze", "<Stock Name> \nGet charts"),
        BotCommand("suggest", "Get charts")
    ])
    # Set menu button to show commands
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# Bot entry point
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("analyze", analyze)) 
    app.add_handler(CommandHandler("suggest", suggest)) 
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.post_init = setup
    app.run_polling()

if __name__ == '__main__':
    logging.info("Bot is starting...")
    # Start the event loop using asyncio.run(main())
    asyncio.run(main())
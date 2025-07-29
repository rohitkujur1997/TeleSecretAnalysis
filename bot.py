import os, asyncio, pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
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

COMMODITY_TICKERS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "crude oil": "CL=F",
    "natural gas": "NG=F",
    "copper": "HG=F",
    "aluminum": "ALI=F",
}


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
    db.collection("TeleSecretAnalysis").document(str(user_id)).set({
        "Membership": False,
        "FNO": 'Both',
        "AVERAGE": 20,
        "STARTDATE":10,
        "STARTMONTH":5,
        "ENDDATE":30,
        "ENDMONTH":6,
        "bot_started": today_str
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

def download_monthly_databargraph(ticker, start_year, end_year):
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    yearly_data = {}

    for year in range(start_year, end_year + 1):
        start = f"{year}-01-01"
        end = datetime.today().strftime('%Y-%m-%d') if year == end_year else f"{year}-12-31"

        # Download daily data (not monthly) to get first and last trading days of each month
        df = yf.download(ticker, start=start, end=end, interval='1d', progress=False)
        if df.empty:
            continue

        df['Year'] = df.index.year
        df['Month'] = df.index.month

        # Group by month to get first and last closing prices
        monthly_changes = []
        for month in sorted(df['Month'].unique()):
            month_df = df[df['Month'] == month]
            first_close = month_df['Close'].iloc[0]
            last_close = month_df['Close'].iloc[-1]
            percent_change = ((last_close - first_close) / first_close) * 100

            monthly_changes.append({
                'Month': months[month - 1],  # Get month abbreviation
                'Percent Change': round(percent_change, 2)
            })

        # Convert to DataFrame and store
        monthly_df = pd.DataFrame(monthly_changes)
        monthly_df['Month'] = pd.Categorical(monthly_df['Month'], categories=months, ordered=True)
        monthly_df.sort_values('Month', inplace=True)
        yearly_data[year] = monthly_df

    return yearly_data



async def plot_yearly_grid(yearly_data, type, ticker,update:Update,context:ContextTypes.DEFAULT_TYPE):
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
        if type == "C":
            ax.set_ylabel("Price (USD)")
        else:
            ax.set_ylabel("Price (INR)")
        ax.grid(True)

    for i in range(len(yearly_data), len(axes)):
        fig.delaxes(axes[i])

    plt.tight_layout()
    if type == "C":
        filename = f"{ticker.replace('=F','')}_years_charts.png"
    else:
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


# Make sure this version of calculate_yearly_percent_change is used
def calculate_yearly_percent_change(yearly_data):
    results = []

    for year, df in yearly_data.items():
        df = df.copy()
        df.index = pd.to_datetime(df.index)

        # Filter strictly to current year
        df = df[df.index.year == year]
        df_sorted = df.sort_values('Month')

        if df_sorted.empty or 'Close' not in df_sorted.columns:
            continue

        start_price = df_sorted['Close'].iloc[0]
        end_price = df_sorted['Close'].iloc[-1]

        if pd.notna(start_price) and pd.notna(end_price) and start_price != 0:
            percent_change = ((end_price - start_price) / start_price) * 100
            results.append({'Year': year, '% Change': round(percent_change, 2)})

    return pd.DataFrame(results)


# Async function for Telegram bot
async def plot_annual_changes_grouped_by_year(update, context, all_yearly_data, ticker_symbols, cols=2, figsize=(12, 6)):
    # Step 1: Aggregate yearly % changes by year across all tickers
    yearly_results = {}  # {year: {ticker: %change}}

    for ticker in ticker_symbols:
        yearly_data = all_yearly_data.get(ticker, {})
        df_temp = calculate_yearly_percent_change(yearly_data)

        for _, row in df_temp.iterrows():
            year = row['Year']
            change = row['% Change']

            if year not in yearly_results:
                yearly_results[year] = {}
            yearly_results[year][ticker] = change

    if not yearly_results:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No valid data to plot.")
        return

    # Step 2: Prepare subplot layout
    years_sorted = sorted(yearly_results.keys())
    rows = (len(years_sorted) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=figsize, constrained_layout=True)
    axes = axes.flatten()

    # Step 3: Plot each year’s data
    for i, year in enumerate(years_sorted):
        ax = axes[i]
        data = yearly_results[year]

        tickers = list(data.keys())
        changes = [data[t] for t in tickers]
        colors = ['green' if val > 0 else 'red' for val in changes]

        bars = ax.bar(tickers, changes, color=colors)

        for bar, value in zip(bars, changes):
            try:
                # Convert height to plain Python float
                height_raw = bar.get_height()
                if hasattr(height_raw, "item"):  # numpy scalar
                    height = float(height_raw.item())
                else:
                    height = float(height_raw)
            except Exception:
                height = 0.0

            va = 'bottom' if height > 0 else 'top'

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f"{value:.2f}%",
                ha='center',
                va=va,
                fontsize=8
            )

        ax.axhline(0, color='black', linestyle='--', linewidth=0.8)
        ax.set_title(f"Year: {year}")
        ax.set_xlabel("Ticker")
        if i % cols == 0:
            ax.set_ylabel("% Change")
        ax.grid(axis='y', linestyle='--', alpha=0.5)

    # Step 4: Remove unused axes
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    # Step 5: Save and send
    filename = f"yearly_change_grouped_by_year.png"
    plt.savefig(filename, dpi=300, format='png')
    plt.close(fig)
    logging.info(f"Saved image: {filename}, Size: {os.path.getsize(filename)} bytes")

    with open(filename, 'rb') as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    await context.bot.send_message(chat_id=update.effective_chat.id, text="📊 Yearly % Change by Ticker")

    os.remove(filename)



async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n@{update.effective_user.username if update.effective_user.username else 'No username'}'s Analyze Menu. (`{update.effective_user.id}`)\n"
                                   f"📲 Choose an Option from Main Menu:",
                                   parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("GOLD (Commodity)",callback_data='GOLD'),InlineKeyboardButton("SILVER (Commodity)",callback_data='SILVER')],
                                                [InlineKeyboardButton("CRUDE OIL (Commodity)",callback_data='CRUDEOIL'),InlineKeyboardButton("NATURAL GAS (Commodity)",callback_data='NATURALGAS')],
                                                [InlineKeyboardButton("COPPER (Commodity)",callback_data='COPPER'),InlineKeyboardButton("ALUMINUM (Commodity)",callback_data='ALUMINUM')],
                                                [InlineKeyboardButton("Stock (Equity)", callback_data='set_STOCK')],
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
    return

async def analysis(value,start_year,type,update:Update,context:ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        ticker = value
        current_year = datetime.today().year
        #start_year = 1995

        yearly_data = download_monthly_data(ticker, start_year, current_year)
        await plot_yearly_grid(yearly_data,type, ticker,update,context)    
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ *Analysis completed successfully!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
            ])
        )
    except Exception as ex:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error: {ex}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
            ])
            )
        
async def analysisbargraph(ticker_symbols, start_year, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        tickers = [ticker_symbols]
        await context.bot.send_message(
                chat_id=chat_id,
                text=f"{tickers}")
        all_yearly_data = {ticker: download_monthly_databargraph(ticker, start_year, 2024) for ticker in tickers}
        await context.bot.send_message(
                chat_id=chat_id,
                text=f"{all_yearly_data}")
        await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Analysis completed successfully!*")
        await plot_annual_changes_grouped_by_year(update,context,all_yearly_data, tickers, cols=2)
        await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Analysis completed successfully!*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                ])
            )
    except Exception as ex:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error: {ex}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
            ])
            )


def get_nearest_close(date, df):
    while date not in df.index and date >= df.index.min():
        date -= timedelta(days=1)
    return df.loc[date]['Close'] if date in df.index else None

async def checkyearly(ticker_symbols,update:Update,context:ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
    start_day, start_month = data.get("STARTDATE", 0), data.get("STARTMONTH", 0)
    end_day, end_month = data.get("ENDDATE", 0), data.get("ENDMONTH", 0)
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
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=f"Skipped {ticker_symbol} {year} due to error: {e}",
                                                    reply_markup=InlineKeyboardMarkup([
                                                        [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                                    ]))
                    continue

            all_results[ticker_symbol] = pd.DataFrame(results).sort_values('Year')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Skipped {ticker_symbol} {year} due to error: {e}",
                                                    reply_markup=InlineKeyboardMarkup([
                                                        [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                                    ]))
            continue
    if len(ticker_symbols)>1:
        user_id = update.effective_user.id
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        Avg = data.get("AVERAGE", 0)
        """ # Merge all results into a single DataFrame
        combined_df = pd.DataFrame({'Year': sorted([r['Year'] for r in results])})
        for symbol in ticker_symbols:
            df_temp = all_results[symbol]
            combined_df[symbol] = df_temp['% Change'].values """
        # Merge all results by 'Year'
        combined_df = pd.DataFrame({'Year': list(range(end_date.year - years_back, end_date.year))})

        for symbol in ticker_symbols:
            if symbol in all_results:
                df_temp = all_results[symbol]
                combined_df = combined_df.merge(df_temp, on='Year', how='left').rename(columns={'% Change': symbol})
        
        """ await send_long_message(context, update.effective_chat.id,combined_df.to_string(index=False)) """
        # Calculate and print average percentage change for each stock
        avg_changes = combined_df.drop(columns=['Year']).mean()
        ticker_symbols = [symbol for symbol in ticker_symbols if avg_changes[symbol] >= Avg]

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

async def suggestion(ticker_symbols,update:Update,context:ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
    start_day, start_month = data.get("STARTDATE", 0), data.get("STARTMONTH", 0)
    end_day, end_month = data.get("ENDDATE", 0), data.get("ENDMONTH", 0)
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
                    await context.bot.send_message(chat_id=update.effective_chat.id,
                                                   text=f"Skipped {ticker_symbol} {year} due to error: {e}",
                                                    reply_markup=InlineKeyboardMarkup([
                                                        [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                                    ]))
                    continue

            all_results[ticker_symbol] = pd.DataFrame(results).sort_values('Year')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Skipped {ticker_symbol} {year} due to error: {e}",
                                                    reply_markup=InlineKeyboardMarkup([
                                                        [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                                    ]))
            continue
    if len(ticker_symbols)>1:
        user_id = update.effective_user.id
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        Avg = data.get("AVERAGE", 0)
        """ # Merge all results into a single DataFrame
        combined_df = pd.DataFrame({'Year': sorted([r['Year'] for r in results])})
        for symbol in ticker_symbols:
            df_temp = all_results[symbol]
            combined_df[symbol] = df_temp['% Change'].values """
        # Merge all results by 'Year'
        combined_df = pd.DataFrame({'Year': list(range(end_date.year - years_back, end_date.year))})

        for symbol in ticker_symbols:
            if symbol in all_results:
                df_temp = all_results[symbol]
                combined_df = combined_df.merge(df_temp, on='Year', how='left').rename(columns={'% Change': symbol})
        
        """ await send_long_message(context, update.effective_chat.id,combined_df.to_string(index=False)) """
        # Calculate and print average percentage change for each stock
        avg_changes = combined_df.drop(columns=['Year']).mean()
        ticker_symbols = [symbol for symbol in ticker_symbols if avg_changes[symbol] >= Avg]

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


def get_yf_data(ticker, start_date, end_date):
    try:
        df = yf.download(ticker, start=start_date, end=end_date, interval="1d", progress=False)
        df = df[['Close']].dropna()
        return df
    except Exception as e:
        print(f"[ERROR] Could not fetch data: {e}")
        return None
    
""" async def analyze_all_commodities(start_day, start_month, end_day, end_month, update:Update, context:ContextTypes.DEFAULT_TYPE):
    try:
        today = datetime.today()
        years_back = 10
        start_fetch_date = datetime(today.year - years_back, start_month, start_day)

        n = len(COMMODITY_TICKERS)
        cols = 2
        rows = (n + 1) // cols

        fig, axs = plt.subplots(rows, cols, figsize=(12, rows * 4))
        axs = axs.flatten()

        for i, (commodity_name, ticker) in enumerate(COMMODITY_TICKERS.items()):
            await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Processing {commodity_name.title()}...")
            df = get_yf_data(ticker, start_fetch_date, today)
            if df is None or df.empty:
                await context.bot.send_message(chat_id=update.effective_chat.id,text=f"[ERROR] No data for {commodity_name}")
                continue

            results = []
            for year in range(today.year - 1, today.year - years_back - 1, -1):
                try:
                    d1 = datetime(year, start_month, start_day)
                    d2 = datetime(year, end_month, end_day)

                    nearest_d1 = df.index[df.index.get_indexer([d1], method='nearest')[0]]
                    nearest_d2 = df.index[df.index.get_indexer([d2], method='nearest')[0]]

                    close1 = df.loc[nearest_d1]['Close']
                    close2 = df.loc[nearest_d2]['Close']

                    pct_change = ((close2 - close1) / close1) * 100
                    results.append({'Year': year, '% Change': round(pct_change, 2)})
                except Exception as e:
                    await context.bot.send_message(chat_id=update.effective_chat.id,text=f"[WARN] Skipping {year} for {commodity_name}: {e}")
                    continue

            if not results:
                axs[i].set_title(f"{commodity_name.title()} (No data)")
                axs[i].axis('off')
                continue

            results_df = pd.DataFrame(results).sort_values("Year")
            years = results_df["Year"].astype(str)
            changes = results_df["% Change"].astype(float)
            colors = ['green' if x > 0 else 'red' for x in changes]

            axs[i].bar(years, changes, color=colors)
            axs[i].axhline(0, color='black', linestyle='--', linewidth=0.7)
            axs[i].set_title(f"{commodity_name.title()} (% Change)")
            axs[i].set_ylabel("% Change")
            axs[i].tick_params(axis='x', rotation=45)

        # Hide unused subplots
        for j in range(i + 1, len(axs)):
            axs[j].axis('off')

        plt.suptitle(f"Commodity % Change: {start_day}/{start_month} to {end_day}/{end_month} (Last {years_back} Years)", fontsize=14)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(str(update.effective_chat.id)+"suggestion.png", dpi=300)
        suggestionimg=str(update.effective_chat.id)+"suggestion.png"
        logging.info(f"Saved image: {suggestionimg}, Size: {os.path.getsize(suggestionimg)} bytes")

        # Send as media group
        with open(suggestionimg, 'rb') as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f)
        #plt.show()
        
        # Clean up
        os.remove(suggestionimg)
        await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ *Suggestions have been generated based on your settings.!*",
                parse_mode="Markdown"
            )
        await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Go back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Error Occur: {e}\nGo back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))

async def suggestCom(update:Update, context:ContextTypes.DEFAULT_TYPE):
    client = TelegramClient(StringSession(), api_id, api_hash)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await client.connect()
    doc = db.collection("TeleSecretAnalysis").document(str(user_id)).get()
    if not doc.exists:
        set_user_payment(user_id)
    data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
    Membership = data.get("Membership", False)
    if Membership:
        start_day, start_month = data.get("STARTDATE", 0), data.get("STARTMONTH", 0)
        end_day, end_month = data.get("ENDDATE", 0), data.get("ENDMONTH", 0)
        await context.bot.send_message(chat_id=chat_id,text="MCX Commodity Analyzer (Multi-Commodity View)\n")
        await analyze_all_commodities(start_day, start_month, end_day, end_month, update, context)
    else:
        await context.bot.send_message(
                chat_id=chat_id,
                text="🔒 Access Denied: Your *membership is inactive*. Please activate it to proceed.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                    ])
            ) """

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
        FNO = data.get("FNO", '')
        Membership = data.get("Membership", False)
        Avg = data.get("AVERAGE", 0)
        sd = data.get("STARTDATE", 0)
        sm = data.get("STARTMONTH", 0)
        ed = data.get("ENDDATE", 0)
        em = data.get("ENDMONTH", 0)

        await context.bot.send_message(chat_id=chat_id,
            text=(
            "🙌 *Welcome to the TeleSecretAnalysis Bot!*\n\n"
            "Here you can analyze any listed Indian stock. 🚀\n\n"
            "📢 *Devs Group:* @\n\n"
            f"💼 *Account ID:* `{user_id}`\n"
            f"🔢 *FNO:* `{FNO}`\n"
            f"🎟️ *Membership:* `{Membership}`\n"
            f"📊 *Average:* `{Avg}`%\n"
            f"📅 *Start Date:* `{sd}`, {sm} (dd, mm)\n"
            f"📅 *End Date:* `{ed}`, {em} (dd, mm)\n"
            "📌 *Commands to Get Started:*\n"
            "`/start` – To Start the Bot\n"
            "`/help` – See all available commands 🆘\n\n"
            f"🔗 *Invite Link:* `https://t.me/{context.bot.username}?start={user_id}`"),
            parse_mode="Markdown"
            )
        """
        await context.bot.send_message(chat_id=chat_id,text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n@{update.effective_user.username if update.effective_user.username else 'No username'}'s Menu. (`{user_id}`)",
                                            parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))"""
        await mainMenu(update, context) 
    except Exception as e:
        await update.message.reply_text(f"Session error: {e}")
        await client.disconnect()
        return
    
async def mainMenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n@{update.effective_user.username if update.effective_user.username else 'No username'}'s Menu. (`{update.effective_user.id}`)\n"
                                   f"📲 Choose an Option from Main Menu:",
                                   parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("My Settings",callback_data='showsettings'),InlineKeyboardButton("Change Settings",callback_data='setsettings')],
                                                #[InlineKeyboardButton("📊 Suggest All Commodities(based on settings)", callback_data='suggestCom')],
                                                [InlineKeyboardButton(f"📊 Suggest From StockList\n🗓 1995–2024\n⚙️ Based on settings", callback_data='suggest')],
                                                [InlineKeyboardButton("📊 Check Specific Stock (based on settings)", callback_data='checksuggested')],
                                                [InlineKeyboardButton("📈 Analyze Yearly Graph", callback_data='ANALYZE'),InlineKeyboardButton("Help", callback_data='help')]
                                            ]))
    return

async def specificStock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n@{update.effective_user.username if update.effective_user.username else 'No username'}'s Menu. (`{update.effective_user.id}`)\n"
                                   f"📲 Check Specific Stock 📊 Bar chart (⚙️ based on settings):",
                                   parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("🗓 ListedYear-2024 (between setting dates)", callback_data='set_SUGGESTED')],                                                
                                                [InlineKeyboardButton("🗓 ListedYear-2024 (Each Month % change)", callback_data='checkyearly')],
                                                [InlineKeyboardButton("Main Menu", callback_data='mainMenu')]
                                            ]))
    return

# This function is triggered when button is clicked
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.message.delete()  # Deletes the previous message with the button
        await query.answer()          # Acknowledge the callback to remove the loading state

    user_id = query.from_user.id
    chat_id = update.effective_chat.id

    if query.data == "mainMenu":
        await mainMenu(update,context)
    elif query.data == "help":
        await help(update,context)
    elif query.data == "showsettings":
        await showsettings(update,context)
    elif query.data == "setsettings":
        await setsettings(update,context)
    elif query.data == "suggest":
        await suggest(update,context)
    elif query.data == "checksuggested":
        await specificStock(update,context)
    elif query.data == "checkyearly":
        await checkyearly(["bhel.NS"],update,context)
    #elif query.data == "suggestCom":
    #    await suggestCom(update,context)
    elif query.data == "ANALYZE":
        await analyze(update,context)
    #elif query.data == "GOLD":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing GOLD...")
    #    await analysis("GC=F",1995,"C",update,context)
    #elif query.data == "SILVER":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing SILVER...")
    #    await analysis("SI=F",1995,"C",update,context)
    #elif query.data == "CRUDEOIL":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing CRUDE OIL...")
    #    await analysis("CL=F",1995,"C",update,context)
    #elif query.data == "NATURALGAS":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing NATURAL GAS...")
    #    await analysis("NG=F",1995,"C",update,context)
    #elif query.data == "COPPER":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing COPPER...")
    #    await analysis("HG=F",1995,"C",update,context)
    #elif query.data == "ALUMINUM":
    #    await context.bot.send_message(chat_id=chat_id,text="Analyzing ALUMINUM...")
    #    await analysis("ALI=F",1995,"C",update,context)
    elif query.data == 'set_FNO':
        await context.bot.send_message(chat_id=chat_id,text="Select anyone option:",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Want FNO Stock",callback_data='Yes')],
                                                [InlineKeyboardButton("Dont want FNO Stock",callback_data='No')],
                                                [InlineKeyboardButton("Want Both",callback_data='Both')],
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
    elif query.data == 'Both' or query.data == 'Yes' or query.data == 'No':
        # Toggle FNO directly (example of immediate action)
        user_ref = db.collection("TeleSecretAnalysis").document(str(user_id))
        doc = user_ref.get()
        if doc.exists:
            #current_value = doc.to_dict().get("FNO", False)
            user_ref.update({"FNO": query.data})
            await context.bot.send_message(chat_id=chat_id,text=f"✅ FNO set to `{query.data}`.", parse_mode="Markdown")
            await context.bot.send_message(chat_id=chat_id,text=f"Go back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
        else:
            set_user_payment(user_id)
            await context.bot.send_message(chat_id=chat_id,text="🔄 User profile created. Please try again.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
    else:
        # Ask for value input in next message
        context.user_data["pending_setting"] = query.data.replace("set_", "")
        pending_setting = context.user_data['pending_setting']

        # Base message
        text = f"📝 Please send the value for *{pending_setting}*:"
        # Add extra info if the setting is STOCK
        if pending_setting == "STOCK":
            text += " (also add year separated with space)"
        await context.bot.send_message(chat_id=chat_id,text=text, parse_mode="Markdown")
            
async def handle_setting_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_setting" not in context.user_data:
        return

    setting = context.user_data["pending_setting"]
    value = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_ref = db.collection("TeleSecretAnalysis").document(str(user_id))
    doc = user_ref.get()

    if not doc.exists:
        set_user_payment(user_id)
        await context.bot.send_message(chat_id=chat_id,text="🔄 User profile created. Please try again.",
                                       parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Change Settings",callback_data='setsettings')]
                                            ]))
        return

    if setting in ["AVERAGE", "STARTDATE", "STARTMONTH", "ENDDATE", "ENDMONTH"]:
        if not value.isnumeric():
            await context.bot.send_message(chat_id=chat_id,text="⚠️ Invalid input: Must be numeric.",
                                           parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Change Settings",callback_data='setsettings')]
                                            ]))
            return
        user_ref.update({setting.upper(): int(value)})
    elif setting in ["STOCK", "SUGGESTED"]:
        if setting == "STOCK":
            try:
                v=value.split()
                if len(v)==2:
                    await analysis(v[0]+".NS",int(v[1]),"S",update,context)
                    await analysisbargraph(v[0]+".NS",int(v[1]),update,context)
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Error!!!\n"
                        f"Looks like u have not entered 'Start year' after STOCK NAME.\n"
                        f"Eg. `BHEL 2021`",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                            ])
                        )
                return
            except Exception as e:
                await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Error!!!\n"
                        f"Looks like u have entered invalid 'Start year' after STOCK NAME.\n"
                        f"Error msg: {e}\n"
                        f"Eg. `BHEL 2021`",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                            ])
                        )
        if setting == "SUGGESTED":
            await suggested(value,update,context)
            return
    else:
        await context.bot.send_message(chat_id=chat_id,text="⚠️ Invalid setting.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Change Settings",callback_data='setsettings')]
                                            ]))
        return

    await context.bot.send_message(chat_id=chat_id,text=f"✅ *{setting}* updated to `{value}`.", parse_mode="Markdown")
    await context.bot.send_message(chat_id=chat_id,text=f"Go back to Change Settings.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Change Settings",callback_data='setsettings')]
                                            ]))
    context.user_data.pop("pending_setting", None)


async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        await client.connect()
        user_id = update.effective_user.id
        doc = db.collection("TeleSecretAnalysis").document(str(user_id)).get()
        if not doc.exists:
            set_user_payment(user_id)
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        Membership = data.get("Membership", False)
        if Membership:
            client = TelegramClient(StringSession(), api_id, api_hash)
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            await client.connect()
            values = []
            #data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
            FNO = data.get("FNO", '')

            # Open the CSV file
            with open("output_data.csv", newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header (row 1)

                for row in reader:
                    if len(row) >= 4 and row[3].strip().upper() == "TRUE" and (FNO == "Yes" or FNO == "Both"):
                        values.append(row[0])
                        continue
                    if len(row) >= 4 and row[3].strip().upper() == "FALSE" and (FNO == "No" or FNO == "Both"):
                        values.append(row[0])
                        continue
            ticker_symbols = [item + ".NS" for item in values]                        
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔍 *Analyzing {len(ticker_symbols)} stocks* based on your FNO settings...",
                parse_mode="Markdown"
            )
            await suggestion(ticker_symbols,update,context)
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Suggestions have been generated based on your settings.!*",
                parse_mode="Markdown"
            )
            await context.bot.send_message(chat_id=chat_id,text=f"Go back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔒 Access Denied: Your *membership is inactive*. Please activate it to proceed.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                    ])
            )

    except Exception as e:
        if type(e).__name__ == "ValueError" and e == "Number of rows must be a positive integer, not 0":
            await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Error!!!\n"
                    f"Fix your Settings\n"
                    f"Maybe Your Average is too high according to other settings causing no data return.\n"
                    f"Goto Main Menu then change settings.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                        ])
                    )
        else:
            await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Error: {e}\n"
                    f"Type: {type(e).__name__}\n"
                    f"Start both with /start command.")
        await client.disconnect()

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n@{update.effective_user.username if update.effective_user.username else 'No username'}'s Help Screen. (`{update.effective_user.id}`)",
                                   reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ])
                                            )

async def showsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id        
        doc = db.collection("TeleSecretAnalysis").document(str(user_id)).get()
        if not doc.exists:
            set_user_payment(user_id)
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        FNO = data.get("FNO", '')
        Membership = data.get("Membership", False)
        Avg = data.get("AVERAGE", 0)
        sd = data.get("STARTDATE", 0)
        sm = data.get("STARTMONTH", 0)
        ed = data.get("ENDDATE", 0)
        em = data.get("ENDMONTH", 0)
        await context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"🙌 *Welcome to the TeleSecretAnalysis Bot!*\n"
            f"📋 *@{update.effective_user.username if update.effective_user.username else 'No username'}'s Settings. (`{update.effective_user.id}`):*\n\n"
            f"🔢 *FNO:* `{FNO}`\n"
            f"📊 *Average:* `{Avg}`%\n"
            f"📅 *Start Date:* `{sd}`, {sm} (dd, mm)\n"
            f"📅 *End Date:* `{ed}`, {em} (dd, mm)\n"
            f"🎟️ *Membership:* `{Membership}`",
            parse_mode="Markdown")
        await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Go back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
    except Exception as e:
        context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"⚠️ Error: {e}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                ]))

async def suggested(value,update:Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        await client.connect()
        user_id = update.effective_user.id
        doc = db.collection("TeleSecretAnalysis").document(str(user_id)).get()
        if not doc.exists:
            set_user_payment(user_id)
        data = db.collection("TeleSecretAnalysis").document(str(user_id)).get().to_dict()
        Membership = data.get("Membership", False)
        if Membership:
            client = TelegramClient(StringSession(), api_id, api_hash)
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            await client.connect()
            with open("output_data.csv", newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # Skip header (row 1)
                for row in reader:
                    if value.upper() in row[0]:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"🏢 *Company Name:* `{row[1]}`\n"
                                f"🏭 *Industry:* `{row[2]}`"
                            ),
                            parse_mode="Markdown"
                        )
            ticker_symbols = [value+".NS"]
                #await context.bot.send_message(chat_id=chat_id,text=ticker_symbols)
            await suggestion(ticker_symbols,update,context)
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ *Suggestions have been generated based on your settings.!*",
                parse_mode="Markdown"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Go back to Main Menu.",
                                            reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                                            ]))
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔒 Access Denied: Your *membership is inactive*. Please activate it to proceed.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                    ])
            )
    except Exception as ex:
        await client.disconnect()
        await context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"⚠️ Error: {ex}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                ]))

async def setsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        keyboard = [
            [InlineKeyboardButton("Set FNO", callback_data='set_FNO')],
            [InlineKeyboardButton("Set AVERAGE", callback_data='set_AVERAGE')],
            [InlineKeyboardButton("Set STARTDATE", callback_data='set_STARTDATE')],
            [InlineKeyboardButton("Set STARTMONTH", callback_data='set_STARTMONTH')],
            [InlineKeyboardButton("Set ENDDATE", callback_data='set_ENDDATE')],
            [InlineKeyboardButton("Set ENDMONTH", callback_data='set_ENDMONTH')],
            [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"🛠 Choose a setting to update:", reply_markup=reply_markup)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id,text=f"⚠️ Error: {e}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu",callback_data='mainMenu')]
                ]))

async def membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = context.args[0]
        user_ref = db.collection("TeleSecretAnalysis").document(str(user_id))
        doc = user_ref.get()
        if doc.exists:        
            data = doc.to_dict()
            Membership = data.get("Membership", False)
            user_ref.update({"Membership": not Membership})
        await update.message.reply_text(f"Membership status changed")
        await context.bot.send_message(chat_id=user_id,text=f"Membership status changed")
    except Exception as e:
            await update.message.reply_text(f"⚠️ Error: Member not exist")

async def send_long_message(client, entity, message, chunk_size=4096):
    for i in range(0, len(message), chunk_size):
        await client.send_message(entity, message[i:i+chunk_size])

async def setup(application):
    # Set commands
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("menu", "Display Main Menu"),
        BotCommand("help", "Show help information")
        #BotCommand("analyze", "Analyze a stock (e.g., /analyze TCS)"),
        #BotCommand("suggest", "Get stock suggestions"),
        #BotCommand("showsettings", "View your current settings"),
        #BotCommand("setsettings", "Update your settings")sawathi
    ])
    # Set menu button to show commands
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# Bot entry point
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("menu", mainMenu)) 
    app.add_handler(CommandHandler("suggest", suggest)) 
    app.add_handler(CommandHandler("showsettings", showsettings)) 
    app.add_handler(CommandHandler("setsettings", setsettings)) 
    app.add_handler(CommandHandler("membership", membership)) #/membership <user_id>
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_setting_value))

    app.post_init = setup
    app.run_polling()

if __name__ == '__main__':
    logging.info("Bot is starting...")
    # Start the event loop using asyncio.run(main())
    asyncio.run(main())

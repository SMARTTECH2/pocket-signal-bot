import time
from datetime import datetime, timedelta
import yfinance as yf
from telegram import Bot
from telegram.error import TelegramError

# ========== YOUR CONFIGURATION ==========
TELEGRAM_TOKEN = "Alexander Smart💠:
Deepsek

ALEXANDERSMITH Glo:
8519743273:AAHrq5wIch4KzbK11Mzuc-EwgR14mD8ZtTI"
CHAT_ID = "-1002187734732"

# Trading parameters
ASSETS = ['EURUSD=X', 'GBPUSD=X', 'BTC-USD']  # Yahoo Finance symbols
# Note: Yahoo uses 'EURUSD=X' for forex, 'BTC-USD' for crypto.
TRADE_DIRECTION = 'both'                       # 'call', 'put', or 'both'
RISK_PER_TRADE = 0.02                           # 2% of simulated balance per signal
MAX_CONCURRENT_TRADES = 3
MAX_DAILY_LOSS = 0.05                            # 5% daily loss limit
MAX_DRAWDOWN = 0.15                               # 15% max drawdown from peak
MIN_BALANCE_TO_TRADE = 10                         # minimum simulated balance
EXPIRY_MINUTES = 5                                 # signal expiry in minutes
PAYOUT_RATE = 0.80                                  # typical Pocket Option payout (80%)

# ========== SIMULATED STATE ==========
sim_balance = 1000.0               # starting simulated balance
account_peak = sim_balance
daily_start_balance = sim_balance
daily_loss = 0.0
active_trades = []                  # open simulated trades
trade_log = []                       # completed trades

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)

# ========== HELPER FUNCTIONS ==========

def get_current_price(asset):
    """
    Fetch the latest price for a given symbol using Yahoo Finance.
    """
    ticker = yf.Ticker(asset)
    data = ticker.history(period="1d", interval="1m")
    if data.empty:
        raise Exception(f"No data for {asset}")
    return data['Close'].iloc[-1]

def valid_session():
    """
    Decide if trading is allowed (e.g., market hours).
    For now, always return True.
    You can customize this to check time of day, weekends, etc.
    """
    # Example: only trade on weekdays during certain hours
    now = datetime.now()
    # if now.weekday() >= 5:  # Saturday=5, Sunday=6
    #     return False
    # if now.hour < 8 or now.hour > 20:
    #     return False
    return True

def scan_market():
    """
    YOUR SIGNAL GENERATION LOGIC GOES HERE.
    This function should return a list of signals.
    Each signal is a dict with keys: 'pair' (asset symbol) and 'direction' ('call' or 'put').
    If no signals, return an empty list.
    """
    signals = []
    # Example: if price above 200-period moving average -> CALL, else PUT
    # This is just a placeholder – replace with your own strategy.
    for asset in ASSETS:
        price = get_current_price(asset)
        # Get historical data for MA calculation
        ticker = yf.Ticker(asset)
        hist = ticker.history(period="1d", interval="5m")
        if len(hist) < 200:
            continue
        ma200 = hist['Close'].rolling(200).mean().iloc[-1]
        if price > ma200:
            direction = 'call'
        else:
            direction = 'put'
        signals.append({'pair': asset, 'direction': direction})
    return signals[:3]  # limit to top 3 (or implement your own ranking)

def check_risk_limits():
    """Return True if new signals are allowed based on simulated risk."""
    global sim_balance, account_peak, daily_start_balance, daily_loss

    if sim_balance > account_peak:
        account_peak = sim_balance

    drawdown = (account_peak - sim_balance) / account_peak
    if drawdown >= MAX_DRAWDOWN:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Max drawdown reached ({drawdown:.2%}). No new signals.")
        return False

    daily_loss_pct = (daily_start_balance - sim_balance) / daily_start_balance
    if daily_loss_pct >= MAX_DAILY_LOSS:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Daily loss limit reached ({daily_loss_pct:.2%}). No more signals today.")
        return False

    if sim_balance < MIN_BALANCE_TO_TRADE:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Simulated balance too low ({sim_balance}). No new signals.")
        return False

    if len(active_trades) >= MAX_CONCURRENT_TRADES:
        bot.send_message(chat_id=CHAT_ID, text="⚠️ Max concurrent simulated trades reached. No new signals.")
        return False

    return True

def calculate_stake():
    """Calculate stake based on current simulated balance."""
    stake = sim_balance * RISK_PER_TRADE
    return round(stake, 2)

def send_signal(signal):
    """
    Send a trading signal via Telegram and create a simulated trade.
    """
    asset = signal['pair']
    direction = signal['direction']
    stake = calculate_stake()
    entry_price = get_current_price(asset)
    expiry_time = datetime.now() + timedelta(minutes=EXPIRY_MINUTES)

    global sim_balance
    sim_balance -= stake

    active_trades.append({
        'asset': asset,
        'direction': direction,
        'stake': stake,
        'entry_price': entry_price,
        'expiry': expiry_time,
        'placed_at': datetime.now()
    })

    msg = (f"🔔 SIGNAL: {direction.upper()} {asset}\n"
           f"Entry: {entry_price:.5f}\n"
           f"Stake: {stake} (risk {RISK_PER_TRADE*100:.0f}%)\n"
           f"Expires in {EXPIRY_MINUTES} min")
    bot.send_message(chat_id=CHAT_ID, text=msg)

def check_results():
    """
    Check all simulated trades for expiry, determine win/loss,
    update simulated balance and log results.
    """
    global active_trades, trade_log, sim_balance, daily_loss, account_peak

    now = datetime.now()
    completed = []

    for trade in active_trades:
        if now >= trade['expiry']:
            expiry_price = get_current_price(trade['asset'])
            entry_price = trade['entry_price']

            if trade['direction'] == 'call':
                win = expiry_price > entry_price
            else:
                win = expiry_price < entry_price

            if win:
                profit = trade['stake'] * PAYOUT_RATE
                result = 'win'
            else:
                profit = -trade['stake']
                result = 'loss'
                daily_loss += trade['stake']

            sim_balance += trade['stake'] + profit

            trade_log.append({
                'asset': trade['asset'],
                'direction': trade['direction'],
                'stake': trade['stake'],
                'entry': entry_price,
                'exit': expiry_price,
                'result': result,
                'profit': profit,
                'expiry': trade['expiry']
            })

            completed.append(trade)

            emoji = "✅" if win else "❌"
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"{emoji} {trade['asset']} {trade['direction'].upper()} expired\n"
                     f"Entry: {entry_price:.5f}  Exit: {expiry_price:.5f}\n"
                     f"Result: {result.upper()}  P&L: {profit:.2f}\n"
                     f"Sim Balance: {sim_balance:.2f}"
            )

    active_trades = [t for t in active_trades if t not in completed]

def session_summary():
    """Send a summary of all simulated trades."""
    total = len(trade_log)
    wins = len([t for t in trade_log if t['result'] == 'win'])
    losses = len([t for t in trade_log if t['result'] == 'loss'])
    total_pnl = sum(t['profit'] for t in trade_log)
    acc = (wins / total * 100) if total > 0 else 0

    msg = (f"📊 SIMULATED SESSION SUMMARY\n"
           f"Trades: {total}\n"
           f"Wins: {wins}✅  Losses: {losses}❌\n"
           f"Accuracy: {acc:.1f}%\n"
           f"Total P&L: {total_pnl:.2f}\n"
           f"Current Sim Balance: {sim_balance:.2f}")
    bot.send_message(chat_id=CHAT_ID, text=msg)

# ========== MAIN LOOP ==========

if __name__ == "__main__":
    print("Bot started. Press Ctrl+C to stop.")
    while True:
        try:
            if valid_session():
                if check_risk_limits():
                    top3 = scan_market()
                    if top3:
                        for signal in top3:
                            send_signal(signal)
                    else:
                        bot.send_message(chat_id=CHAT_ID, text="🚫 NO TRADE ZONE")
                else:
                    bot.send_message(chat_id=CHAT_ID, text="⛔ Risk limits prevent new signals.")
            else:
                bot.send_message(chat_id=CHAT_ID, text="⏸️ Out of trading session.")

            check_results()
            time.sleep(60)  # wait 1 minute before next loop

        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            break
        except Exception as e:
            print("Error:", e)
            bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Bot error: {e}")
            time.sleep(60)

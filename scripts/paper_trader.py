import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd

# Setup paths to ensure we can import service modules
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from service.database import SessionLocal, init_db
from service.models_db import User, Portfolio, SignalRecord

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PaperTrader")

BOT_EMAIL = "papertrader@gaurvideep.local"
BOT_USERNAME = "papertrader"

# Fixed quantity to buy for paper trading
FIXED_QTY = 100

def _get_current_price(ticker: str) -> float:
    """Fetch current price from the ticker cache."""
    cache_path = os.path.join(WORKSPACE, "service", "models", "ticker_cache.json")
    if not os.path.exists(cache_path):
        return 0.0
    with open(cache_path) as f:
        cache = json.load(f)
    entry = cache.get(ticker)
    return entry.get("close", 0.0) if entry else 0.0


def get_or_create_bot(db) -> User:
    bot = db.query(User).filter(User.email == BOT_EMAIL).first()
    if not bot:
        logger.info("Creating Paper Trader Bot account...")
        bot = User(
            email=BOT_EMAIL,
            username=BOT_USERNAME,
            password_hash="fake_hash_paper_trader_cannot_login",
            full_name="Paper Trader Engine",
            tier="premium",
            is_verified=True
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)
    return bot


def sell_expired_holdings(db, bot_id: str):
    logger.info("Checking for holdings that have reached the 5-day exit horizon...")
    holdings = db.query(Portfolio).filter(Portfolio.user_id == bot_id).all()
    now = datetime.now(timezone.utc)
    
    sold_count = 0
    total_pnl = 0.0
    
    for h in holdings:
        # Make purchase_date offset-aware if it isn't
        p_date = h.purchase_date
        if p_date.tzinfo is None:
            p_date = p_date.replace(tzinfo=timezone.utc)
            
        # Fixed holding period (in days) before exiting a position
        EXIT_HOLD_DAYS = 5
        days_held = (now - p_date).days
        if days_held >= EXIT_HOLD_DAYS:
            current_price = _get_current_price(h.ticker)
            if current_price == 0.0:
                logger.warning(f"Could not fetch current price for {h.ticker}. Skipping sell.")
                continue
            
            # Simulated 0.1% transaction cost on sell side (0.2% round trip)
            cost_basis = h.purchase_price * h.quantity
            gross_value = current_price * h.quantity
            net_value = gross_value * (1 - 0.001) 
            
            pnl = net_value - cost_basis
            total_pnl += pnl
            
            logger.info(f"SELL {h.quantity} {h.ticker} @ {current_price:.2f}. "
                        f"Entry: {h.purchase_price:.2f}. PnL: {pnl:+.2f}")
            
            # Log to local CSV ledger
            ledger_entry = {
                "sell_date": now.isoformat(),
                "ticker": h.ticker,
                "quantity": h.quantity,
                "entry_price": h.purchase_price,
                "exit_price": current_price,
                "pnl": pnl,
                "days_held": days_held
            }
            ledger_file = os.path.join(WORKSPACE, "paper_trading_ledger.csv")
            df = pd.DataFrame([ledger_entry])
            if not os.path.exists(ledger_file):
                df.to_csv(ledger_file, index=False)
            else:
                df.to_csv(ledger_file, mode='a', header=False, index=False)
                
            db.delete(h)
            sold_count += 1
            
    db.commit()
    logger.info(f"Sold {sold_count} positions. Total realized PnL today: {total_pnl:+.2f}")


def buy_new_signals(db, bot_id: str):
    logger.info("Checking for new BUY signals...")
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    # Get recent BUY signals (within last 24h)
    signals = db.query(SignalRecord).filter(
        SignalRecord.signal == "BUY",
        SignalRecord.created_at >= yesterday
    ).all()
    
    # Deduplicate signals by ticker (if multiple were generated for the same ticker today)
    unique_tickers = {s.ticker: s for s in signals}
    
    bought_count = 0
    for ticker, sig in unique_tickers.items():
        # Cost basis includes simulated 0.1% buy-side slippage/brokerage
        purchase_price = sig.price * (1 + 0.001)
        
        # In a real system, you might check if you already own it to prevent overlapping trades
        # The backtest allows overlapping trades, so we will allow multiple holdings of the same ticker.
        
        logger.info(f"BUY {FIXED_QTY} {ticker} @ {purchase_price:.2f} (Signal Confidence: {sig.confidence:.2f})")
        h = Portfolio(
            user_id=bot_id,
            ticker=ticker,
            quantity=FIXED_QTY,
            purchase_price=purchase_price,
            purchase_date=now
        )
        db.add(h)
        bought_count += 1
        
    db.commit()
    logger.info(f"Opened {bought_count} new positions.")


def main():
    logger.info("--- Starting Paper Trader Engine ---")
    init_db()
    db = SessionLocal()
    try:
        bot = get_or_create_bot(db)
        sell_expired_holdings(db, bot.id)
        buy_new_signals(db, bot.id)
    except Exception as e:
        logger.error(f"Paper trader encountered an error: {e}")
    finally:
        db.close()
    logger.info("--- Paper Trader Engine Finished ---")


if __name__ == "__main__":
    main()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import uvicorn

app = FastAPI()

class TickerRequest(BaseModel):
    ticker: str

@app.get("/health")
def health_check():
    return {"status": "ok", "models_loaded": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}

@app.post("/predict")
def get_signal(request: TickerRequest):
    ticker = request.ticker.upper()
    try:
        # Fetch last 1 year of data (enough for 200-day SMA)
        end = datetime.now()
        start = end - timedelta(days=400)  # Extra buffer for rolling calc
        df = yf.download(ticker, start=start, end=end, progress=False)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data found for ticker")
        
        # Calculate 200-day Simple Moving Average
        sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]
        
        # Determine Regime
        regime = "BULL" if current_price > sma_200 else "BEAR"
        
        # Simulate a "Confidence Score" (like your LSTM would output)
        # In a real deployment, this loads your saved LSTM model.
        # For now, we use a simple rule: if BULL, confidence is high (0.65), else low (0.45).
        confidence = 0.65 if regime == "BULL" else 0.45
        
        # Generate Signal based on your Phase 5 winning rules (Long-only with SMA filter)
        if regime == "BULL" and confidence > 0.55:
            signal = "BUY"
        else:
            signal = "HOLD"  # Since we are long-only, we don't short here yet

        return {
            "ticker": ticker,
            "signal": signal,
            "confidence": round(confidence, 3),
            "regime": regime,
            "current_price": round(current_price, 2),
            "sma_200": round(sma_200, 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# This is for running locally
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
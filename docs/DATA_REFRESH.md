# Aarambh Quant — EOD Data Refresh & Cache Architecture

## 1. Overview & Strategy

Aarambh's market signals (specifically the 200-SMA systematic trend filter and mechanical regime classifications) operate exclusively on **Daily Closing Prices (EOD data)**. 

Because systematic regime classification changes only upon daily candle completion, the platform does not require continuous intraday real-time tick streaming. All indicators, SMA distances, and regime states are updated once daily following the National Stock Exchange (NSE) cash market close (15:30 IST).

---

## 2. Automated Pipeline (Primary Path)

The primary data pipeline is an automated **GitHub Actions Workflow** located at:
[`.github/workflows/refresh_cache.yml`](../.github/workflows/refresh_cache.yml)

### Workflow Specifications:
- **Schedule:** Runs Monday through Friday at `13:00 UTC` (`18:30 IST`), approximately 3 hours after market close to ensure NSE EOD Bhavcopy and Yahoo Finance candle settlements are finalized.
- **Execution Environment:** `ubuntu-latest` running Python 3.12.
- **Execution Script:** `python rebuild_cache_v2.py`
- **Output Artifacts:**
  1. `service/models/ticker_cache.json` — 138 Nifty 100 tickers with updated closes, 200-SMAs, and technical features.
  2. `service/models/indices_cache.json` — NIFTY 50 and BSE SENSEX EOD closing benchmarks and percentage movements.
- **Validation Guardrails:**
  - The script asserts that at least **100 valid tickers** are successfully fetched and calculated.
  - If network errors, exchange throttles, or upstream data issues yield fewer than 100 tickers, the workflow terminates loudly with exit code 1.
  - The bad/empty cache is **never** committed over the existing operational cache.
- **Deployment Trigger:**
  - Upon successful validation, the action commits the updated JSON files back to the `main` branch with `[skip ci]`.
  - Render monitors the `main` branch (with `autoDeploy: true` configured in `render.yaml`), triggering an automatic container rebuild and redeployment with the fresh EOD market data.

---

## 3. Manual Fallback Procedure

If the GitHub Actions runner ever experiences upstream throttling, IP blocks, or network downtime, the cache can be refreshed manually from any local development machine:

### Step-by-Step Instructions:

1. **Pull Latest Main:**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Execute Rebuild Script:**
   ```bash
   python rebuild_cache_v2.py
   ```
   *The script will iterate through the Nifty 100 universe, calculate technical indicators, validate output volume, and generate both `service/models/ticker_cache.json` and `service/models/indices_cache.json`.*

3. **Verify Generated Files:**
   ```bash
   git status
   ```
   Ensure `service/models/ticker_cache.json` and `service/models/indices_cache.json` show modified status with non-zero byte size.

4. **Commit and Push:**
   ```bash
   git add service/models/ticker_cache.json service/models/indices_cache.json
   git commit -m "chore(data): manual EOD ticker and indices cache refresh"
   git push origin main
   ```
   *Pushing to `main` will automatically trigger Render's build pipeline and update the live web application.*

---

## 4. Compliance & Licensing Notice (EOD vs. Real-Time)

> [!IMPORTANT]
> **Intentionally EOD-Only by Design**
>
> 1. **Regulatory & Terms-of-Service Boundary:**
>    - Broker APIs (such as Zerodha Kite Connect, AngelOne SmartAPI, and Upstox Developer API) are strictly licensed for **personal trading execution and private personal algorithmic bots**. Their Terms of Service explicitly prohibit vending, redistributing, or displaying live market feeds to third-party end users or paying platform subscribers.
>    - Official real-time exchange data vending on open commercial websites requires an enterprise license from **NSE Data & Analytics Limited** (annual fees exceeding ₹29 Lakhs + user exchange fees).
>
> 2. **Alignment with Product Methodology:**
>    - Aarambh's quantitative foundation is the **200-Day SMA systematic trend regime**. Daily closing prices are mathematically sufficient and optimal for this strategy.
>    - **Do NOT attempt to upgrade this pipeline to real-time scraping or broker API tick streaming** without securing an authorized commercial data redistribution license (e.g., TrueData or direct NSE vendor agreement).

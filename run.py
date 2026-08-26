import requests
import json

# =========================================================
# 1. REPLACE with your OpenRouter API key
#    Get it free from: https://openrouter.ai/keys
# =========================================================
API_KEY = ""   # Replace with your OpenRouter key when running locally
# =========================================================
# 2. REPLACE with the Phase 1 prompt from my previous message
#    (the long one that starts with "You are a Senior AI...")
# =========================================================
PROMPT = """You are a Senior AI Infrastructure Engineer. Execute the following tasks sequentially. For each task, provide:
- What you did
- Code you wrote (with file paths)
- Verification steps and output
- Any errors encountered and how you resolved them

TASK 1: Repository Setup
- Clone the official Kronos repository: https://github.com/shiyu-coder/Kronos.git
- Install dependencies from requirements.txt
- Verify installation by running a simple test (e.g., python -c "import kronos; print('OK')")

TASK 2: CSV Pipeline Setup (Recommended for flexibility)
- Clone the CSV fine-tuning pipeline: https://github.com/leeroopedia/workflow-shiyu-coder-kronos-csv-finetuning.git
- Install its requirements
- Verify the config/default.yaml exists and is readable

TASK 3: Data Acquisition
- Choose a market (US stocks, Indian stocks, A-shares, or crypto)
- Write a Python script using yfinance (for US/India) OR akshare/baostock (for A-shares) to fetch:
  - At least 5 years of daily OHLCV data
  - Columns: timestamps, open, high, low, close, volume, amount
- Save the data as data/raw/market_data.csv
- Print summary statistics (row count, date range, any missing values)

TASK 4: Data Splitting
- Write a script that splits the data into:
  - Training: 70% (earliest period)
  - Validation: 15%
  - Test: 15% (latest period - critical for forward-looking evaluation)
- Save as: data/train.csv, data/val.csv, data/test.csv
- Ensure NO overlap between splits
- Print the date ranges for each split

TASK 5: Data Quality Report
- Generate a report containing:
  - Total rows per split
  - Date ranges
  - Any anomalies (missing values, outliers beyond 5 standard deviations)
  - Summary statistics (mean, std, min, max for OHLCV)

OUTPUT FORMAT:
Provide a complete summary of all tasks completed with file paths, code snippets, and verification outputs. End with "PHASE 1 COMPLETE" and a readiness statement for Phase 2."""   # <-- EDIT THIS

# =========================================================
# DO NOT CHANGE ANYTHING BELOW
# =========================================================
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "x-ai/ox-alpha",          # ✅ Correct model ID for Ox Alpha
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 131072
    },
    timeout=600
)

if response.status_code == 200:
    result = response.json()
    output = result['choices'][0]['message']['content']
    # Save to file
    with open("phase1_output.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print("✅ Done! Output saved to phase1_output.txt")
    print(output[:500] + "...\n(Full output in file)")
else:
    print(f"❌ Error {response.status_code}: {response.text}")
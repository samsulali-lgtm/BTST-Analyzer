"""
BTST/Short-Term AI Market Analyzer
Runs before market close, analyzes MCX/NSE instruments and gives buy recommendations.
Uses Google Gemini AI + live data from free APIs.
"""

import os
import json
import requests
from datetime import datetime
import google.generativeai as genai

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Instruments to watch (Yahoo Finance tickers)
WATCHLIST = {
    "MCX Crude Oil":    "CRUDEOIL=F",   # WTI Crude Futures
    "Brent Crude":      "BZ=F",          # Brent Crude Futures
    "Natural Gas":      "NG=F",          # Natural Gas
    "Gold MCX":         "GC=F",          # Gold Futures
    "Silver MCX":       "SI=F",          # Silver Futures
    "Nifty 50":         "^NSEI",         # Nifty Index
    "Bank Nifty":       "^NSEBANK",      # Bank Nifty
    "USD/INR":          "INR=X",         # Dollar Rupee
    "Oil & Gas ETF":    "XLE",           # US Oil & Gas ETF (proxy)
}

# ── Market Data ───────────────────────────────────────────────────────────────
def fetch_price_data(ticker: str) -> dict:
    """Fetch current price + 5-day data from Yahoo Finance (no API key needed)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "interval": "1d",
            "range": "5d",
            "includePrePost": "false"
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        closes = result["indicators"]["quote"][0]["closes"] if "closes" in result["indicators"]["quote"][0] else result["indicators"]["quote"][0].get("close", [])
        
        closes = [c for c in closes if c is not None]
        current = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        prev_close = meta.get("chartPreviousClose", closes[-2] if len(closes) > 1 else current)
        
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        
        return {
            "ticker": ticker,
            "current_price": round(current, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "5d_closes": [round(c, 2) for c in closes[-5:]],
            "52w_high": meta.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low": meta.get("fiftyTwoWeekLow", "N/A"),
            "volume": meta.get("regularMarketVolume", "N/A"),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def fetch_news_headlines() -> list:
    """Fetch latest financial/geopolitical headlines from NewsAPI (free tier)."""
    news_api_key = os.environ.get("NEWS_API_KEY", "")
    if not news_api_key:
        return ["NewsAPI key not configured — skipping news fetch."]
    
    queries = ["crude oil market", "India stock market", "gold silver commodities", "geopolitical risk oil"]
    headlines = []
    
    for q in queries:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": q,
                "sortBy": "publishedAt",
                "pageSize": 3,
                "apiKey": news_api_key,
                "language": "en"
            }
            r = requests.get(url, params=params, timeout=10)
            articles = r.json().get("articles", [])
            for a in articles:
                headlines.append(f"[{q.upper()}] {a['title']} — {a['source']['name']}")
        except:
            pass
    
    return headlines[:12]  # Top 12 headlines


def fetch_fear_greed() -> str:
    """Fetch CNN Fear & Greed Index (proxy for market sentiment)."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        score = r.json()["fear_and_greed"]["score"]
        rating = r.json()["fear_and_greed"]["rating"]
        return f"{score:.1f}/100 — {rating.upper()}"
    except:
        return "Unavailable"


# ── AI Analysis ───────────────────────────────────────────────────────────────
def run_ai_analysis(market_data: dict, headlines: list, fear_greed: str) -> str:
    """Send all data to Gemini and get BTST recommendations."""
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=(
            "You are an expert Indian market analyst specializing in BTST (Buy Today Sell Tomorrow) "
            "and short-term commodity/equity trades on MCX and NSE. Be specific, data-driven, and concise. "
            "Focus on MCX commodities and Nifty/BankNifty options. Do NOT add disclaimers. "
            "Give analysis like a professional trader would."
        )
    )

    now = datetime.now().strftime("%A, %d %B %Y %H:%M IST")
    market_summary = json.dumps(market_data, indent=2)
    news_summary = "\n".join(headlines)

    prompt = f"""
## Today's Date & Time
{now}

## Live Market Data (prices as of now)
{market_summary}

## Latest Market News & Headlines
{news_summary}

## Market Sentiment
CNN Fear & Greed Index: {fear_greed}

---

## YOUR TASK:
Analyze ALL the above data and provide a concise, actionable BTST report with the following sections:

### 1. 🌍 MARKET OVERVIEW (2-3 lines)
Quick macro picture — what's driving markets today?

### 2. 🛢️ COMMODITY ANALYSIS
For each key commodity (Crude Oil, Gold, Silver, Natural Gas):
- Current trend (bullish/bearish/neutral)
- Key level to watch
- BTST view

### 3. 📈 TOP BTST PICKS FOR TONIGHT
Give exactly 3-5 actionable BTST picks in this format:

**[Instrument Name]**
- Action: BUY CALL / BUY PUT / BUY STOCK / AVOID
- Strike (if options): e.g., 6500 CE
- Entry Zone: ₹XXX - ₹XXX
- Target: ₹XXX (+X%)
- Stop Loss: ₹XXX (-X%)
- Confidence: High / Medium / Low
- Reason: (2-3 lines explaining WHY this pick)

### 4. ⚠️ KEY RISKS TO WATCH OVERNIGHT
What events/data could reverse the trade? (US data, geopolitical, OPEC, etc.)

### 5. 🎯 OVERALL MARKET BIAS FOR TOMORROW
Bullish / Bearish / Neutral with a 1-line summary
"""

    response = model.generate_content(prompt)
    return response.text


# ── Telegram Notification ─────────────────────────────────────────────────────
def send_telegram(message: str):
    """Send the analysis report to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram not configured — printing to console only.")
        return
    
    # Telegram has 4096 char limit — split if needed
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                print("✅ Telegram message sent!")
            else:
                print(f"❌ Telegram error: {r.text}")
        except Exception as e:
            print(f"❌ Telegram exception: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🤖 BTST AI MARKET ANALYZER — Starting...")
    print(f"⏰ Time: {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
    print("=" * 60)

    # 1. Fetch market data
    print("\n📡 Fetching live market data...")
    market_data = {}
    for name, ticker in WATCHLIST.items():
        data = fetch_price_data(ticker)
        market_data[name] = data
        change = data.get("change_pct", 0)
        arrow = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        print(f"  {arrow} {name}: {data.get('current_price', 'N/A')} ({change:+.2f}%)")

    # 2. Fetch news
    print("\n📰 Fetching latest news headlines...")
    headlines = fetch_news_headlines()
    print(f"  Found {len(headlines)} headlines")

    # 3. Fetch sentiment
    print("\n😨 Fetching Fear & Greed Index...")
    fear_greed = fetch_fear_greed()
    print(f"  Fear & Greed: {fear_greed}")

    # 4. AI Analysis
    print("\n🧠 Running Gemini AI analysis...")
    analysis = run_ai_analysis(market_data, headlines, fear_greed)

    # 5. Print report
    print("\n" + "=" * 60)
    print("📊 BTST AI REPORT")
    print("=" * 60)
    print(analysis)

    # 6. Send to Telegram
    header = f"🤖 *BTST AI REPORT — {datetime.now().strftime('%d %b %Y')}*\n\n"
    send_telegram(header + analysis)

    # 7. Save report to file
    report_file = f"btst_report_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(report_file, "w") as f:
        f.write(f"BTST AI Report — {datetime.now().strftime('%d %b %Y %H:%M')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(analysis)
    print(f"\n💾 Report saved to: {report_file}")

    print("\n✅ BTST Analyzer complete!")


if __name__ == "__main__":
    main()

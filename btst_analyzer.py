"""
BTST/Short-Term AI Market Analyzer — Refined v2
- Focus: Nifty 50 & Bank Nifty options (primary), commodities (secondary)
- Technicals: RSI, MACD, Bollinger Bands computed from Yahoo Finance data
- Style: Conservative — only HIGH confidence picks
- AI: Google Gemini 2.5 Flash Lite
"""

import os
import json
import requests
import math
from datetime import datetime
import google.generativeai as genai

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
genai.configure(api_key=GEMINI_API_KEY)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

WATCHLIST = {
    "Nifty 50":        "^NSEI",
    "Bank Nifty":      "^NSEBANK",
    "Nifty IT":        "^CNXIT",
    "India VIX":       "^INDIAVIX",
    "S&P 500":         "^GSPC",
    "Dow Jones":       "^DJI",
    "NASDAQ":          "^IXIC",
    "USD/INR":         "INR=X",
    "Brent Crude":     "BZ=F",
    "Gold":            "GC=F",
    "Silver":          "SI=F",
}

# ── Technical Indicators ──────────────────────────────────────────────────────

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd(closes, fast=12, slow=26, signal=9):
    def ema(data, span):
        k = 2 / (span + 1)
        r = [data[0]]
        for p in data[1:]:
            r.append(p * k + r[-1] * (1 - k))
        return r
    if len(closes) < slow + signal:
        return None, None, None
    ef = ema(closes, fast)
    es = ema(closes, slow)
    ml = [f - s for f, s in zip(ef, es)]
    sl = ema(ml, signal)
    hist = [m - s for m, s in zip(ml, sl)]
    return round(ml[-1], 4), round(sl[-1], 4), round(hist[-1], 4)


def compute_bollinger(closes, period=20, num_std=2.0):
    if len(closes) < period:
        return None, None, None
    w = closes[-period:]
    mean = sum(w) / period
    std = math.sqrt(sum((x - mean)**2 for x in w) / period)
    return round(mean + num_std*std, 2), round(mean, 2), round(mean - num_std*std, 2)


def compute_technicals(closes):
    rsi = compute_rsi(closes)
    macd, macd_sig, macd_hist = compute_macd(closes)
    bb_u, bb_m, bb_l = compute_bollinger(closes)
    current = closes[-1] if closes else None

    rsi_label = (
        "OVERSOLD" if rsi and rsi < 35 else
        "OVERBOUGHT" if rsi and rsi > 65 else
        "NEUTRAL" if rsi else "N/A"
    )
    macd_label = (
        "BULLISH" if macd and macd_hist and macd_hist > 0 else
        "BEARISH" if macd and macd_hist and macd_hist < 0 else "NEUTRAL"
    )
    bb_label = (
        "NEAR_UPPER" if current and bb_u and current >= bb_u * 0.99 else
        "NEAR_LOWER" if current and bb_l and current <= bb_l * 1.01 else
        "INSIDE"
    )
    return {
        "RSI_14": rsi, "RSI_signal": rsi_label,
        "MACD": macd, "MACD_signal": macd_sig, "MACD_hist": macd_hist, "MACD_bias": macd_label,
        "BB_upper": bb_u, "BB_mid": bb_m, "BB_lower": bb_l, "BB_position": bb_label,
    }


# ── Market Data ───────────────────────────────────────────────────────────────

def fetch_price_data(name, ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        r = requests.get(url, params={"interval":"1d","range":"60d","includePrePost":"false"},
                         headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        result = r.json()["chart"]["result"][0]
        meta   = result["meta"]
        q      = result["indicators"]["quote"][0]

        closes  = [c for c in q.get("close",  []) if c is not None]
        volumes = [v for v in q.get("volume", []) if v is not None]
        highs   = [h for h in q.get("high",   []) if h is not None]
        lows    = [l for l in q.get("low",    []) if l is not None]

        current    = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        prev_close = meta.get("chartPreviousClose",  closes[-2] if len(closes)>1 else current)
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "name": name,
            "current_price": round(current, 2),
            "prev_close":    round(prev_close, 2),
            "change_pct":    round(change_pct, 2),
            "20d_high":      round(max(highs[-20:]), 2) if len(highs) >= 20 else "N/A",
            "20d_low":       round(min(lows[-20:]),  2) if len(lows)  >= 20 else "N/A",
            "52w_high":      meta.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low":       meta.get("fiftyTwoWeekLow",  "N/A"),
            "volume":        volumes[-1] if volumes else "N/A",
            "technicals":    compute_technicals(closes),
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


def fetch_india_vix():
    try:
        r    = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/^INDIAVIX",
                            params={"interval":"1d","range":"5d"},
                            headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        meta = r.json()["chart"]["result"][0]["meta"]
        vix  = meta.get("regularMarketPrice", "N/A")
        prev = meta.get("chartPreviousClose", vix)
        chg  = ((vix - prev) / prev * 100) if prev and vix != "N/A" else 0
        level = ("HIGH — options expensive, avoid buying" if vix > 18 else
                 "LOW — options cheap, ideal to buy"      if vix < 13 else
                 "MODERATE — normal premium")
        return f"{vix} ({chg:+.2f}%) — {level}"
    except:
        return "Unavailable"


def fetch_fii_dii():
    try:
        headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json",
                   "Referer":"https://www.nseindia.com"}
        r    = requests.get("https://www.nseindia.com/api/fiidiiTradeReact",
                            headers=headers, timeout=10)
        data = r.json()
        if data:
            l = data[0]
            fn = l.get("fiiNet","N/A"); dn = l.get("diiNet","N/A")
            fb = "BUYING" if str(fn).lstrip("-").replace(".","").isdigit() and float(fn)>0 else "SELLING"
            db = "BUYING" if str(dn).lstrip("-").replace(".","").isdigit() and float(dn)>0 else "SELLING"
            return f"FII Net: ₹{fn} Cr ({fb}) | DII Net: ₹{dn} Cr ({db})"
    except:
        pass
    return "FII/DII unavailable"


def fetch_news_headlines():
    key = os.environ.get("NEWS_API_KEY","")
    if not key:
        return ["NewsAPI key not set."]
    headlines = []
    for q in ["Nifty BankNifty India stock market","RBI India economy","FII DII India markets","India inflation rupee"]:
        try:
            r = requests.get("https://newsapi.org/v2/everything",
                             params={"q":q,"sortBy":"publishedAt","pageSize":3,"apiKey":key,"language":"en"},
                             timeout=10)
            for a in r.json().get("articles",[]):
                headlines.append(f"[{q[:20].upper()}] {a['title']} — {a['source']['name']}")
        except:
            pass
    return headlines[:12]


def fetch_fear_greed():
    try:
        r  = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                          headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        fg = r.json()["fear_and_greed"]
        return f"{fg['score']:.0f}/100 — {fg['rating'].upper()}"
    except:
        return "Unavailable"


# ── AI Analysis ───────────────────────────────────────────────────────────────

def run_ai_analysis(market_data, vix, fii_dii, headlines, fear_greed):
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction="""You are a senior NSE options trader with 15 years experience.
PRIMARY focus: Nifty 50 and Bank Nifty options ONLY.

STRICT RULES:
1. Only recommend trades with CONFLUENCE of 3+ technical signals agreeing
2. NEVER give a call pick if RSI > 68 (overbought)
3. NEVER give a put pick if RSI < 32 (oversold)
4. NEVER recommend buying options when India VIX > 20
5. MAX 2-3 picks only — quality over quantity
6. If signals are mixed or unclear — say AVOID and explain why
7. Always size entry based on VIX level
8. Be brutally honest — no forced trades"""
    )

    now = datetime.now().strftime("%A, %d %B %Y %H:%M IST")

    prompt = f"""
## DATE & TIME: {now}

## INDIA VIX: {vix}
## FII/DII: {fii_dii}
## GLOBAL SENTIMENT: CNN Fear & Greed = {fear_greed}

## LIVE MARKET DATA + TECHNICALS:
{json.dumps(market_data, indent=2)}

## NEWS:
{chr(10).join(headlines)}

---

Generate a CONSERVATIVE BTST report focused on Nifty & BankNifty options:

### 1. 📊 TECHNICAL SNAPSHOT — NIFTY & BANKNIFTY

For each:
| Indicator | Value | Signal |
|-----------|-------|--------|
| RSI 14    | XX    | Neutral/Overbought/Oversold |
| MACD      | XX    | Bullish/Bearish crossover |
| Bollinger | XX    | Near upper/lower/inside |
| 20D High  | XX    | Near resistance? |
| 20D Low   | XX    | Near support? |

Technical Bias: BULLISH / BEARISH / NEUTRAL

### 2. 🌍 MACRO IN 3 LINES
Global cues + FII/DII + VIX impact on options premium

### 3. 🎯 BTST PICKS (MAX 2-3, HIGH CONFIDENCE ONLY)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Instrument] [Strike] [CE/PE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action     : BUY / AVOID
Entry Zone : ₹XX - ₹XX
Target     : ₹XX (+X%)
Stop Loss  : ₹XX (-X%)
Risk/Reward: 1:X
Confidence : HIGH ✅

Signals aligned:
  RSI    → XX (signal)
  MACD   → (bullish/bearish)
  BB     → (position)
  Price  → (near support/resistance level)
  VIX    → (premium impact)

Reason: [2 specific lines from the data above]
Exit if: [exact invalidation level]

### 4. ⛔ DO NOT TRADE IF:
[Specific conditions that cancel all picks]

### 5. 🗓️ TOMORROW'S BIAS: BULLISH / BEARISH / NEUTRAL
[One line reason]
"""

    return model.generate_content(prompt).text


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram not configured.")
        return
    for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                timeout=10
            )
            print("✅ Telegram sent!" if r.status_code == 200 else f"❌ {r.text}")
        except Exception as e:
            print(f"❌ {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🤖 BTST AI v2 — Conservative | Equity Focus | Technicals")
    print(f"⏰ {datetime.now().strftime('%d %b %Y %H:%M:%S')}")
    print("=" * 60)

    print("\n📡 Fetching data + computing RSI / MACD / Bollinger...")
    market_data = {}
    for name, ticker in WATCHLIST.items():
        d = fetch_price_data(name, ticker)
        market_data[name] = d
        chg = d.get("change_pct", 0)
        rsi = d.get("technicals", {}).get("RSI_14", "?")
        macd_bias = d.get("technicals", {}).get("MACD_bias", "?")
        arrow = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
        print(f"  {arrow} {name}: {d.get('current_price','N/A')} ({chg:+.2f}%) | RSI:{rsi} | MACD:{macd_bias}")

    print("\n📊 India VIX..."); vix = fetch_india_vix(); print(f"  {vix}")
    print("\n💰 FII/DII..."); fii_dii = fetch_fii_dii(); print(f"  {fii_dii}")
    print("\n📰 News..."); headlines = fetch_news_headlines(); print(f"  {len(headlines)} headlines")
    print("\n😨 Fear & Greed..."); fear_greed = fetch_fear_greed(); print(f"  {fear_greed}")

    print("\n🧠 Gemini AI analyzing (conservative mode)...")
    analysis = run_ai_analysis(market_data, vix, fii_dii, headlines, fear_greed)

    print("\n" + "=" * 60)
    print(analysis)

    header = (
        f"🤖 *BTST CONSERVATIVE REPORT — {datetime.now().strftime('%d %b %Y')}*\n"
        f"⏰ {datetime.now().strftime('%H:%M IST')} | Focus: Nifty & BankNifty\n\n"
    )
    send_telegram(header + analysis)

    fname = f"btst_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(fname, "w") as f:
        f.write(header.replace("*","") + analysis)
    print(f"\n💾 Saved: {fname}\n✅ Done!")


if __name__ == "__main__":
    main()

# 🤖 BTST AI Market Analyzer

An AI-powered system that runs **automatically before Indian market close** and sends you actionable BTST (Buy Today Sell Tomorrow) picks via **Telegram**.

Built with **Claude AI + GitHub Actions + Yahoo Finance + NewsAPI**.

---

## 🕐 When It Runs

| Session | IST Time | Purpose |
|---|---|---|
| NSE/BSE Pre-Close | **3:15 PM IST** | Equity BTST picks |
| MCX Pre-Close | **11:15 PM IST** | Commodity picks (Crude, Gold, Silver) |
| Manual | Anytime | Run on demand from GitHub |

---

## 📲 What You Get (on Telegram)

Every evening before market close, you'll receive a report like:

```
🤖 BTST AI REPORT — 02 Mar 2026

🌍 MARKET OVERVIEW
Crude surging on Iran-US tensions. Global risk-on with commodity bias.

🛢️ COMMODITY ANALYSIS
Crude Oil: BULLISH — Key level 6400. BTST: Strong Buy
Gold: NEUTRAL — Watch 85,000. BTST: Hold

📈 TOP BTST PICKS

**CRUDEOILM 6500 CE (17 Mar)**
- Action: BUY CALL
- Entry Zone: ₹380 - ₹400
- Target: ₹550 (+40%)
- Stop Loss: ₹300 (-25%)
- Confidence: High
- Reason: Geopolitical premium building, OI surge at 6400-6500, ...

⚠️ KEY RISKS
- US inventory data at 8 PM IST
- Iran ceasefire announcement risk

🎯 TOMORROW'S BIAS: BULLISH
```

---

## ⚙️ Setup (5 minutes)

### Step 1: Fork / Create GitHub Repo
Create a new GitHub repository and add these files.

### Step 2: Add GitHub Secrets
Go to your repo → **Settings → Secrets → Actions → New repository secret**

| Secret Name | Where to Get | Required? |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | ✅ Required |
| `TELEGRAM_BOT_TOKEN` | Create bot via @BotFather on Telegram | ✅ Recommended |
| `TELEGRAM_CHAT_ID` | Get from @userinfobot on Telegram | ✅ Recommended |
| `NEWS_API_KEY` | https://newsapi.org (free tier) | Optional |

### Step 3: Get Your Telegram Bot
1. Open Telegram, search **@BotFather**
2. Send `/newbot` → follow instructions → copy the **token**
3. Search **@userinfobot** → send any message → copy your **chat ID**
4. Add both to GitHub secrets

### Step 4: Enable GitHub Actions
- Go to your repo → **Actions tab** → Enable workflows

### Step 5: Test It!
- Go to **Actions → BTST AI Market Analyzer → Run workflow**
- Check the logs and your Telegram!

---

## 🔧 Customizing the Watchlist

Edit `scripts/btst_analyzer.py` and modify the `WATCHLIST` dict:

```python
WATCHLIST = {
    "MCX Crude Oil":    "CRUDEOIL=F",
    "Gold MCX":         "GC=F",
    "Nifty 50":         "^NSEI",
    # Add more Yahoo Finance tickers here
    "Reliance":         "RELIANCE.NS",
    "ONGC":             "ONGC.NS",
}
```

---

## 📁 File Structure

```
btst-ai-system/
├── .github/
│   └── workflows/
│       └── btst_analyzer.yml    ← GitHub Actions schedule
├── scripts/
│   └── btst_analyzer.py         ← Main AI analysis script
├── requirements.txt
└── README.md
```

---

## ⚠️ Disclaimer
This is an AI-powered tool for **informational purposes only**. Always do your own research. Past performance does not guarantee future results. Options trading involves significant risk.

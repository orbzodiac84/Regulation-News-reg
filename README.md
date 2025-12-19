# MarketPulse-Reg (Pilot)

금융 규제 분석 및 알림 시스템

## 🚀 Getting Started

### 1. Backend (Data Collector & Scheduler)
Requires Python 3.10+ and configured `.env`.

```bash
# Activate Virtual Environment (Windows)
venv\Scripts\activate

# Install Dependencies (First time only)
pip install -r requirements.txt

# Run Scheduler (Collects every 10 min)
python src/scheduler.py
```

### 2. Frontend (Web Dashboard)
Requires Node.js 18+.

```bash
cd web

# Install Dependencies (First time only)
npm install

# Run Development Server
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000).
**Passcode**: `marketpulse1234`

## 📂 Project Structure
- `config/`: Agency RSS configurations.
- `src/collectors/`: RSS Parser & HTML Scraper.
- `src/services/`: Gemini Analyzer & Telegram Notifier.
- `web/`: Next.js Web Dashboard.

## 🛠 Features
- **5 Agencies**: FSC, FSS, MOEF, BOK, MAFRA.
- **Analysis**: Gemini-based impact analysis for Banking sector.
- **Notification**: Telegram alerts.
- **Dashboard**: Simple list view with Passcode protection.

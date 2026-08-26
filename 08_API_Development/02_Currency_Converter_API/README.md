<div align="center">

# 💱 Currency Converter API

### A Python desktop application for real-time currency conversion with historical rates, conversion history, and export capabilities.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![ExchangeRate-API](https://img.shields.io/badge/ExchangeRate--API-00d9a5?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Currency Converter is a Python desktop application that provides real-time currency conversion using exchange rate APIs.

The application supports:
- **Real-time Conversion**: Convert between 150+ currencies with live rates
- **Multiple API Sources**: Primary (ExchangeRate-API) with automatic fallback
- **Historical Rates**: View past exchange rates for specific dates
- **Conversion History**: Track all your conversions with timestamps
- **Export**: Save conversions, rates, and history to CSV or JSON
- **Popular Currencies**: Quick access to 20 major currencies
- **Rate Caching**: 1-hour cache to minimize API calls

---

# ✨ Features

- **Currency Conversion**: Convert any amount between supported currencies
- **Live Exchange Rates**: Real-time rates from ExchangeRate-API with fallback
- **Currency Search**: Select from 20 popular currencies or type any ISO code
- **Swap Currencies**: One-click currency swap
- **Conversion History**: Automatic tracking of all conversions
- **Rate Display**: Current exchange rate with 1 base = X target format
- **Auto-Conversion**: Real-time conversion as you type
- **Export Options**:
  - Single conversion (CSV/JSON)
  - All rates for base currency (CSV/JSON)
  - Conversion history (CSV/JSON)
- **Keyboard Shortcuts**: Efficient workflow
- **Fullscreen Mode**: Immersive experience
- **Modern Dark Theme**: Easy on the eyes

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter (GUI with custom dark theme)
- Requests (HTTP client)
- python-dotenv (environment variables)
- CSV / JSON (data export)
- Logging
- Threading (non-blocking GUI)
- Type hints
- Dataclasses

---

# 📂 Project Structure

```text
02_Currency_Converter_API/
│
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── api_client.py       # Exchange rate API client
│   ├── models.py           # Data models (dataclasses)
│   ├── tracker.py          # Conversion coordination
│   ├── exporter.py         # CSV/JSON export
│   ├── logger.py           # Logging setup
│   ├── utils.py            # Utility functions
│   ├── colors.py           # Color theme
│   └── controls.py         # Custom Tkinter widgets
│
├── tests/
│   ├── conftest.py
│   ├── test_utils.py
│   ├── test_models.py
│   └── test_exporter.py
│
├── logs/
├── exports/
├── README.md
├── requirements.txt
├── .gitignore
└── .env.example
```

---

# ⚙️ Environment Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔑 API Key Setup

1. Sign up at [ExchangeRate-API](https://www.exchangerate-api.com/) for a free API key
2. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Edit `.env` and add your API key:
   ```
   EXCHANGE_RATE_API_KEY=your_api_key_here
   ```

**Note**: The app works without an API key using a free fallback service (exchangerate-api.com), but with limited features.

---

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 API Endpoints Used

- **Primary (ExchangeRate-API v6)**:
  - Latest rates: `https://v6.exchangerate-api.com/v6/{key}/latest/{base}`
  - Pair rate: `https://v6.exchangerate-api.com/v6/{key}/pair/{from}/{to}`
  - Historical: `https://v6.exchangerate-api.com/v6/{key}/history/{base}/{date}`
  - Supported codes: `https://v6.exchangerate-api.com/v6/{key}/codes`

- **Fallback (exchangerate-api.com)**:
  - Latest rates: `https://api.exchangerate-api.com/v4/latest/{base}`

---

# 📊 Supported Currencies

20 Popular Currencies (quick select):
- USD, EUR, GBP, JPY, CHF, CAD, AUD, CNY, INR, BRL
- MXN, SGD, HKD, KRW, TRY, ZAR, NOK, SEK, DKK, PLN

Plus 150+ additional currencies via API.

---

# 📤 Export

### CSV
Structured tabular data for spreadsheet analysis.

### JSON
Structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "conversion": {
    "from_currency": "USD",
    "to_currency": "EUR",
    "amount": 100.0,
    "result": 92.34,
    "rate": 0.9234,
    ...
  }
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + N | Focus amount entry |
| Ctrl + R | Refresh rates |
| Ctrl + E | Export conversion |
| Ctrl + H | Export history |
| F11 | Toggle fullscreen |
| Escape | Exit fullscreen |
| Enter | Convert (in amount field) |
| Type | Auto-convert |

---

# 📋 Requirements

```text
requests>=2.31.0
python-dotenv>=1.0.0
```

Install all requirements:

```bash
pip install -r requirements.txt
```

---

# 🧪 Testing

Run tests with pytest:

```bash
pytest tests/ -v
```

Or run specific test modules:

```bash
pytest tests/test_utils.py -v
pytest tests/test_models.py -v
pytest tests/test_exporter.py -v
```

**Test Coverage**: 39 tests passing covering utils, models, and exporter modules.

---

# 🎯 Learning Outcomes

- REST API consumption with primary/fallback strategy
- HTTP requests with error handling and retry logic
- JSON parsing and data validation with dataclasses
- Threading for responsive GUI during API calls
- Tkinter custom widget development (ConversionCard, SwapButton)
- Modern dark theme UI design with color-coded elements
- Environment variable management for API keys
- CSV/JSON data export with metadata
- Exponential backoff retry strategy
- Rate caching with TTL
- Conversion history persistence
- Currency formatting (symbols, decimals per currency)
- Modular application architecture
- Type hints and comprehensive documentation

---

# 🔄 Application Workflow

```text
Select From/To Currency
         ↓
Enter Amount
         ↓
Auto-convert / Press Convert
         ↓
Fetch Pair Rate (API)
         ↓
Calculate Result
         ↓
Update Display + History
         ↓
Export (Optional)
```

---

# 🚀 Future Improvements

- Historical rate charts
- Multiple amount conversion (batch)
- Currency alerts/notifications
- Offline mode with cached rates
- Cryptocurrency support
- Portfolio tracking
- Exchange fee calculator
- Multi-language support
- System tray integration
- Command-line interface
- Docker containerization

---

# ⚠️ API Limitations

**ExchangeRate-API Free Tier**:
- 1,500 requests/month
- Hourly updates
- 150+ currencies

**Fallback (exchangerate-api.com)**:
- No API key required
- Limited to latest rates only
- No historical data

The app implements caching (1 hour) and automatic fallback to stay within limits.

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python API Development Project

</div>
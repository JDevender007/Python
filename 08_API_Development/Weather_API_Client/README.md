<div align="center">

# 🌤️ Weather API Client

### A Python desktop application for fetching current weather, forecasts, and city search using the OpenWeatherMap API with a modern GUI.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![OpenWeatherMap](https://img.shields.io/badge/OpenWeatherMap-API-FF6B00?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Weather API Client is a Python desktop application that consumes the OpenWeatherMap API to provide:

- **Current Weather**: Real-time temperature, humidity, pressure, wind, visibility, and conditions
- **5-Day Forecast**: 3-hour interval forecasts with detailed metrics
- **City Search**: Find cities worldwide with geocoding
- **Export**: Save data to CSV or JSON for analysis

The application features a modern dark theme GUI built with Tkinter, rate limiting, caching, and comprehensive error handling.

---

# ✨ Features

- **Current Weather**: Temperature, feels-like, min/max, humidity, pressure, wind, visibility, clouds, sunrise/sunset
- **5-Day Forecast**: 3-hour intervals grouped by day with precipitation probability
- **City Search**: Geocoding with country/state display
- **Units**: Metric (°C, m/s) and Imperial (°F, mph) support
- **Popular Cities**: Quick access to major world cities
- **Export**: CSV and JSON export for current weather, forecast, and search results
- **Caching**: 5-minute cache to reduce API calls
- **Rate Limiting**: Exponential backoff retry logic
- **Keyboard Shortcuts**: Efficient navigation
- **Fullscreen Mode**: Immersive viewing
- **Logging**: File and console logging

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
01_Weather_API_Client/
│
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── api_client.py       # OpenWeatherMap API client
│   ├── models.py           # Data models (dataclasses)
│   ├── tracker.py          # Data fetching coordination
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

1. Sign up at [OpenWeatherMap](https://openweathermap.org/api) for a free API key
2. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Edit `.env` and add your API key:
   ```
   OPENWEATHER_API_KEY=your_api_key_here
   ```

**Note**: The app will work without an API key but will show an error when fetching data.

---

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 API Endpoints Used

- **Current Weather**: `https://api.openweathermap.org/data/2.5/weather`
- **5-Day Forecast**: `https://api.openweathermap.org/data/2.5/forecast`
- **Geocoding**: `https://api.openweathermap.org/geo/1.0/direct`
- **Reverse Geocoding**: `https://api.openweathermap.org/geo/1.0/reverse`

---

# 📊 Data Fields

## Current Weather
- City name, country, coordinates
- Temperature, feels-like, min/max
- Humidity, pressure, visibility
- Wind speed, direction, gust
- Cloud coverage
- Weather condition + description
- Sunrise, sunset, timezone
- Data timestamp

## Forecast (3-hour intervals)
- Date, time
- Temperature, feels-like, min/max
- Pressure, humidity
- Weather condition + description
- Wind speed, direction
- Cloud coverage
- Precipitation probability

## City Search
- Name, country, state
- Latitude, longitude

---

# 📤 Export

### CSV
Structured tabular data with headers for easy spreadsheet import.

### JSON
Structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "city": "London",
  "country": "GB",
  "temperature": 15.5,
  ...
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Search City |
| Ctrl + R | Refresh Current |
| Ctrl + E | Export Data |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |
| Enter | Search (in city entry) |
| Double-click | Select city from search results |

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

**Test Coverage**: 55 tests passing covering utils, models, and exporter modules.

---

# 🎯 Learning Outcomes

- REST API consumption with Python
- HTTP requests with error handling
- JSON parsing and data validation
- Dataclass-based data modeling
- Threading for responsive GUI
- Tkinter custom widget development
- Modern dark theme UI design
- Environment variable management
- CSV/JSON data export
- Retry logic with exponential backoff
- Caching strategies
- Logging configuration
- Modular application architecture
- Type hints and documentation

---

# 🔄 Application Workflow

```text
Enter City Name / Select Popular City
              ↓
        Geocoding API
              ↓
    Current Weather API
              ↓
       5-Day Forecast API
              ↓
        Display in GUI
              ↓
       Export CSV / JSON
```

---

# 🚀 Future Improvements

- Weather maps/radar integration
- Historical weather data
- Weather alerts/notifications
- Multiple location tracking
- Weather comparison
- Charts/graphs for temperature trends
- Offline mode with cached data
- Weather widgets
- Command-line interface
- Docker containerization
- CI/CD pipeline

---

# ⚠️ API Limitations

Free OpenWeatherMap tier:
- 60 calls/minute
- 1,000,000 calls/month
- Current weather + 5-day forecast
- No historical data

The app implements caching and rate limiting to stay within limits.

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python API Development Project

</div>
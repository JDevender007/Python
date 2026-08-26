<div align="center">

# 🎬 IMDb Movie Scraper

### A Python desktop application for scraping movie data from IMDb Top 250 chart with detailed information, ratings, and export capabilities.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-success?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

IMDb Movie Scraper is a Python desktop application designed to collect movie information from the IMDb Top 250 chart.

The application fetches the IMDb Top 250 chart, extracts movie titles, years, ratings, and vote counts, then optionally scrapes detailed information for each movie including genres, duration, director, writers, cast, plot description, certificates, release dates, countries, languages, budget, gross revenue, and poster images. Data can be exported to CSV or JSON format.

The project follows a modular architecture with separate components for scraping, parsing, tracking, exporting, configuration, logging, and the graphical interface.

---

# ✨ Features

- Fetch IMDb Top 250 chart
- Extract movie titles, years, ratings, votes
- Scrape detailed movie information:
  - Genres
  - Duration (runtime)
  - Director
  - Writers
  - Starring actors
  - Plot description
  - Age certificate
  - Release date
  - Production countries
  - Languages
  - Budget
  - Gross worldwide revenue
  - Poster image URL
- Display results in sortable table
- View detailed movie information on double-click
- Export to CSV
- Export to JSON
- Request timeout handling
- HTTP error handling
- Rate limiting (polite scraping)
- Activity logging
- Progress indicator
- Fullscreen mode
- Keyboard shortcuts
- Modular Python architecture

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter (GUI)
- Requests (HTTP)
- BeautifulSoup4 (HTML Parsing)
- lxml (Parser backend)
- CSV / JSON (Export)
- Logging
- Threading (Non-blocking GUI)

---

# 📂 Project Structure

```text
IMDb_Movie_Scraper/
│
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── scraper.py          # HTTP scraping logic
│   ├── parser.py           # HTML parsing logic
│   ├── tracker.py          # Scraping workflow coordination
│   ├── exporter.py         # Data export (CSV/JSON)
│   ├── logger.py           # Logging setup
│   ├── utils.py            # Utility functions
│   ├── colors.py           # Color theme
│   └── controls.py         # Custom Tkinter widgets
│
├── tests/
│   ├── conftest.py
│   ├── test_utils.py
│   ├── test_parser.py
│   └── test_exporter.py
│
├── logs/
├── exports/
├── README.md
├── requirements.txt
└── .gitignore
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

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 Target Website

The application is configured for:

```text
https://www.imdb.com/chart/top/
```

You can enter a different IMDb chart URL through the application.

**Note:** IMDb may block automated requests. The application includes rate limiting and proper headers, but extraction results depend on IMDb's current HTML structure and anti-bot measures.

---

# 📊 Data Fields

## Chart Data (Basic)
- Rank
- Title
- Year
- Rating (/10)
- Votes
- IMDb URL

## Detailed Data
- Genres
- Duration (minutes)
- Director
- Writers
- Stars (top cast)
- Description/Plot
- Certificate (MPAA/BBFC)
- Release Date
- Production Countries
- Languages
- Budget
- Gross Worldwide
- Poster Image URL

---

# 📤 Export

### CSV
Exports all fields with list values joined by semicolons.

### JSON
Exports structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "total_movies": 250,
  "movies": [...]
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Scrape Chart |
| Ctrl + D | Scrape Details |
| Ctrl + E | Export Data |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |
| Double-click / Enter | View Movie Details |

---

# 📋 Requirements

```text
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
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
pytest tests/test_parser.py -v
pytest tests/test_exporter.py -v
```

---

# 🎯 Learning Outcomes

- Web scraping with Python
- HTTP requests with Sessions
- HTML parsing with BeautifulSoup
- CSS selector-based extraction
- Data cleaning and normalization
- Rate limiting and polite scraping
- Threading for responsive GUI
- Tkinter GUI development
- Custom widget creation
- CSV/JSON export
- Logging configuration
- Modular application architecture
- Object-Oriented Programming
- Exception handling
- Type hints

---

# 🔄 Application Workflow

```text
Enter Chart URL
        ↓
Fetch Chart Page
        ↓
Parse Movie List
        ↓
Display in Table
        ↓
Select Movies (optional)
        ↓
Scrape Details
        ↓
Export CSV / JSON
```

---

# 🚀 Future Improvements

- Search functionality
- Filter by genre/year/rating
- Pagination support for other charts
- Actor/Actress filmography scraping
- TV series scraping
- Image downloading
- Database storage (SQLite)
- Scheduled scraping
- Proxy support
- More export formats (Excel, XML)
- Dark/Light theme toggle
- Column visibility toggles
- Sort by any column
- Advanced filtering UI

---

# ⚠️ Legal & Ethical Notice

This project is for educational purposes only. Please respect IMDb's Terms of Service and robots.txt. 

- Use rate limiting (built-in 2 second delay)
- Do not scrape excessively
- Consider using IMDb's official API for production use
- This tool scrapes publicly available data only

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python Web Scraping Project

</div>
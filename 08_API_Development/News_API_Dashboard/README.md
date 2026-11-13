<div align="center">

# 📰 News API Dashboard

### A Python desktop application for news aggregation and search using the NewsAPI with category filtering, country selection, and export capabilities.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![NewsAPI](https://img.shields.io/badge/NewsAPI-00A8E8?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

News API Dashboard is a Python desktop application that aggregates news from thousands of sources using the NewsAPI.

The application provides:
- **Top Headlines**: Browse latest news by country and category
- **Search Everything**: Search across all articles with filters
- **Sources Directory**: Discover available news sources
- **Rich Article Cards**: Title, description, image, source, reading time
- **Export System**: Save articles and sources to CSV or JSON
- **Modern Dark Theme**: Easy on the eyes with color-coded categories

---

# ✨ Features

- **Top Headlines**: Country + category filtering (20 countries, 7 categories)
- **Search Everything**: Full-text search with date range, language, sort options
- **Sources Browser**: Filter sources by country and category
- **Article Cards**: Image, title, description, source, author, time, reading time
- **Relative Time**: "2 hours ago", "3 days ago" format
- **Reading Time**: Estimated reading time per article
- **Domain Display**: Source domain shown on each card
- **Export Options**: CSV/JSON for articles, sources, search results
- **Rate Limit Friendly**: Caching and efficient API usage
- **Keyboard Shortcuts**: Efficient navigation

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter (GUI with modern dark theme)
- Requests (HTTP client with retry logic)
- python-dotenv (environment variables)
- CSV / JSON (data export)
- Logging
- Threading (non-blocking GUI)
- Type hints
- Dataclasses
- NewsAPI.org

---

# 📂 Project Structure

```text
04_News_API_Dashboard/
│
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── api_client.py       # NewsAPI client
│   ├── models.py           # Data models (dataclasses)
│   ├── tracker.py          # Data fetching coordination
│   ├── exporter.py         # CSV/JSON export
│   ├── logger.py           # Logging setup
│   ├── utils.py            # Utility functions
│   ├── colors.py           # Dark theme colors
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

1. Sign up at [NewsAPI.org](https://newsapi.org/register) for a free API key
2. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Edit `.env` and add your API key:
   ```
   NEWS_API_KEY=your_api_key_here
   ```

**Free Tier Limits**: 100 requests/day, no commercial use

---

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 API Endpoints Used

- **Top Headlines**: `GET /v2/top-headlines` (country, category)
- **Everything**: `GET /v2/everything` (q, sources, domains, dates, sort)
- **Sources**: `GET /v2/sources` (country, category, language)

---

# 📊 Data Displayed

## Article Cards
- Image (placeholder)
- Title (clickable)
- Description (truncated)
- Source name, author
- Category, country
- Relative time ("2 hours ago")
- Reading time estimate
- Source domain

## Sources
- Name, description
- Category, language, country
- Website URL

---

# 📤 Export

### CSV
Structured tabular data for spreadsheet analysis.

### JSON
Structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "total_articles": 20,
  "articles": [
    {
      "title": "Breaking News",
      "source_name": "BBC News",
      "published_at": "2024-01-15T10:30:00Z",
      ...
    }
  ]
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + F | Focus search |
| Ctrl + R | Refresh headlines |
| Ctrl + E | Export current tab |
| Ctrl + S | Search everything |
| F11 | Toggle fullscreen |
| Escape | Exit fullscreen |
| Enter | Execute search |

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

**Test Coverage**: 36 tests passing covering utils, models, and exporter modules.

---

# 🎯 Learning Outcomes

- NewsAPI.org integration
- Complex query parameter handling
- Pagination and rate limiting
- Dataclass-based data modeling
- Threading for responsive GUI during API calls
- Tkinter custom widget development (ArticleCard, SourceCard)
- Modern dark theme UI design
- CSV/JSON data export with metadata
- Exponential backoff retry strategy
- Response caching with TTL
- Relative time formatting
- Reading time estimation
- Domain extraction from URLs
- Modular application architecture
- Type hints and comprehensive documentation

---

# 🔄 Application Workflow

```text
Select Tab (Headlines / Search / Sources)
         ↓
Configure Filters (Country, Category, Query, Dates)
         ↓
Fetch Articles / Sources (API)
         ↓
Display in Scrollable Cards
         ↓
Click Article → Open in Browser
         ↓
Export Data (CSV/JSON)
```

---

# 🚀 Future Improvements

- Article bookmarking/favorites
- Breaking news notifications
- Saved searches with alerts
- Source credibility ratings
- Language translation
- Text-to-speech for articles
- Offline reading mode
- Dark/Light theme toggle
- Custom RSS feed support
- Newsletter generation
- Sentiment analysis
- Topic clustering
- Export to PDF/Markdown
- Mobile-responsive layout
- Docker containerization
- CI/CD pipeline

---

# ⚠️ API Limitations

**Free Tier (NewsAPI.org)**:
- 100 requests/day
- No commercial use
- Limited to headlines (no full content for some sources)
- 1-month article history

**Developer Tier**: 500 requests/day
**Business Tier**: Unlimited

The app implements:
- Request caching (10 min TTL)
- Efficient pagination
- Graceful error handling

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python API Development Project

</div>
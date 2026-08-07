<div align="center">

# 📰 News Scraper

### A Python desktop application for collecting news article information from webpages and exporting the results to CSV and JSON.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-success?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

News Scraper is a Python desktop application designed to collect article information from news webpages.

The application accepts a webpage URL, downloads the webpage, parses available article information, displays the results, and exports collected data to CSV or JSON.

The project uses a modular architecture with separate components for scraping, parsing, exporting, configuration, logging, and the graphical interface.

---

# ✨ Features

- Enter a news website URL
- Fetch webpage content
- Extract article titles
- Extract article links
- Extract publication dates when available
- Extract article summaries when available
- Display scraped articles
- Export results to CSV
- Export results to JSON
- Request timeout handling
- Error handling
- Activity logging
- Progress indicator
- Fullscreen mode
- Keyboard shortcuts
- Modular Python architecture

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter
- Requests
- BeautifulSoup4
- CSV
- JSON
- Logging

---

# 📂 Project Structure

```text
News_Scraper/
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── scraper.py
│   ├── parser.py
│   ├── exporter.py
│   ├── controls.py
│   ├── config.py
│   ├── colors.py
│   ├── logger.py
│   └── utils.py
│
├── logs/
│
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

# 🌐 Test Website

The application is configured with:

```text
https://news.ycombinator.com/
```

You can enter another webpage URL through the application.

The parser works according to the HTML structure available on the target webpage. Different websites use different layouts, so extraction results vary between websites.

---

# 📤 Export

The application supports:

### CSV

Exports:

- Article title
- Article link
- Publication date
- Article summary

### JSON

Exports the same article information in structured JSON format.

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Scrape News |
| Ctrl + E | Export CSV |
| Ctrl + J | Export JSON |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |

---

# 📋 Requirements

```text
requests
beautifulsoup4
```

Install all requirements:

```bash
pip install -r requirements.txt
```

---

# 🎯 Learning Outcomes

- Web scraping with Python
- HTTP requests
- HTML parsing
- BeautifulSoup
- File exporting
- CSV generation
- JSON generation
- Tkinter GUI development
- Exception handling
- Logging
- Modular application architecture
- Object-Oriented Programming

---

# 🔄 Application Workflow

```text
Enter URL
     ↓
Fetch Webpage
     ↓
Parse HTML
     ↓
Extract Articles
     ↓
Display Results
     ↓
Export CSV / JSON
```

---

# 🚀 Future Improvements

- Support for site-specific parsers
- Keyword filtering
- Category filtering
- Article search
- Pagination support
- Duplicate article detection
- RSS feed support
- Scheduled scraping
- Database storage
- More export formats
- Configurable CSS selectors

---

# 👨‍💻 Author

**Devender J**

Data Analyst | Python Developer | AI & Machine Learning Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ Python Web Scraping Project

</div>
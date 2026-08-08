<div align="center">

# 💼 Job Listing Scraper

### A Python desktop application for collecting job listings from supported job websites and exporting the results to CSV and JSON.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-success?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Job Listing Scraper is a Python desktop application designed to collect job listing information from supported job websites.

The application accepts a job website URL, downloads the webpage, extracts available job information, displays the results, provides keyword and location filtering, and exports the collected data to CSV or JSON.

The project uses a modular architecture with separate components for scraping, parsing, filtering, exporting, configuration, logging, utilities, and the graphical interface.

---

# ✨ Features

- Enter job website URL
- Fetch webpage content
- Extract job titles
- Extract company names
- Extract job locations
- Extract job descriptions
- Extract job links
- Filter jobs by keyword
- Filter jobs by location
- Display job listings
- Export results to CSV
- Export results to JSON
- Request timeout handling
- HTTP error handling
- Activity logging
- Progress indicator
- Fullscreen mode
- Keyboard shortcuts
- Modular project architecture

---

# 🛠 Technologies

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
Job_Listing_Scraper/
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── scraper.py
│   ├── parser.py
│   ├── exporter.py
│   ├── filters.py
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

Create the virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

---

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 Test Websites

The application is configured with:

```text
https://remoteok.com/
```

Other websites might use different HTML structures or restrict automated requests.

A website returning HTTP 403 means the server refused the request. This does not indicate a Python installation problem.

---

# 🔎 Filtering

The application supports two filters.

### Keyword

Searches job titles and company names.

Example:

```text
Python
```

### Location

Searches the job location.

Example:

```text
Remote
```

Both filters work together.

---

# 📤 Export

### CSV

The CSV export contains:

```text
title
company
location
description
link
```

### JSON

The JSON export stores the same job information in structured format.

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Scrape Jobs |
| Ctrl + F | Apply Filters |
| Ctrl + E | Export CSV |
| Ctrl + J | Export JSON |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |

---

# 🔄 Application Workflow

```text
Enter Job Website URL
        ↓
Fetch Webpage
        ↓
Parse HTML
        ↓
Extract Job Listings
        ↓
Display Results
        ↓
Apply Filters
        ↓
Export CSV / JSON
```

---

# 🎯 Learning Outcomes

- HTTP requests with Python
- Web scraping
- HTML parsing
- BeautifulSoup
- CSS selectors
- Data filtering
- CSV generation
- JSON generation
- Tkinter GUI development
- Exception handling
- Logging
- Modular application architecture
- Object-Oriented Programming

---

# 🚀 Future Improvements

- Support for site-specific parsers
- More job websites
- Pagination support
- Duplicate detection
- Salary extraction
- Job type filtering
- Experience-level filtering
- Date filtering
- Database storage
- Scheduled scraping
- RSS and API support
- Advanced search
- Job bookmarking

---

# 👨‍💻 Author

**Devender J**

Data Analyst | Python Developer | AI & Machine Learning Enthusiast

GitHub: https://github.com/JDevender007

---
<div align="center">

# 🛒 Amazon Price Tracker

### A Python desktop application for tracking product prices from supported shopping websites and exporting the results to CSV and JSON.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-success?style=for-the-badge)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-orange?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Amazon Price Tracker is a Python desktop application designed to collect and monitor product price information from supported shopping websites.

The application accepts a product URL, downloads the webpage, parses available product information, displays the results, allows users to set target prices, stores price history, and exports collected data to CSV or JSON.

The project uses a modular architecture with separate components for scraping, parsing, price tracking, database management, exporting, configuration, logging, and the graphical interface.

---

# ✨ Features

- Enter a product website URL
- Fetch webpage content
- Extract product names
- Extract current prices
- Extract product availability
- Extract product links
- Set target prices
- Track current prices
- Track lowest recorded prices
- Record price history
- Compare current price with target price
- Display tracked products
- View price history
- Delete tracked products
- Export results to CSV
- Export results to JSON
- SQLite database storage
- Request timeout handling
- HTTP error handling
- Activity logging
- Dashboard interface
- Status indicators
- Fullscreen mode
- Keyboard shortcuts
- Modular Python architecture

---

# 🛠 Technologies Used

- Python 3.13
- CustomTkinter
- Requests
- BeautifulSoup4
- SQLite
- CSV
- JSON
- Logging

---

# 📂 Project Structure

```text
Amazon_Price_Tracker/
│
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── scraper.py
│   ├── parser.py
│   ├── tracker.py
│   ├── database.py
│   ├── exporter.py
│   ├── controls.py
│   ├── dashboard.py
│   ├── products.py
│   ├── history.py
│   ├── config.py
│   ├── colors.py
│   ├── logger.py
│   └── utils.py
│
├── data/
│
├── logs/
│
├── exports/
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

The application is configured for:

```text
https://www.amazon.in/
```

You can enter a supported product URL through the application.

Different shopping websites use different HTML structures and might restrict automated requests. Extraction results depend on the HTML structure available on the target webpage.

An HTTP 403 response means the server refused the request. This does not indicate a Python installation problem.

---

# 💰 Price Tracking

The application allows users to set a target price for a tracked product.

Example:

```text
Current Price: ₹45,999
Target Price:  ₹40,000
```

The application compares the current price with the target price.

When the current price reaches or falls below the target price, the product receives a target-price status.

The application also records the lowest price found during tracking.

---

# 📈 Price History

The application stores successful price checks in the SQLite database.

Each price history record contains:

- Product ID
- Product price
- Checked date and time

This allows users to monitor price changes for tracked products.

---

# 📤 Export

The application supports:

### CSV

Exports:

- Product name
- Product URL
- Current price
- Target price
- Lowest price
- Availability
- Last checked date
- Created date

### JSON

Exports the same product information in structured JSON format.

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + R | Refresh Data |
| Ctrl + N | Add Product |
| Ctrl + P | Open Products |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |

---

# 📋 Requirements

```text
customtkinter
requests
beautifulsoup4
```

SQLite, CSV, JSON, and Logging are provided through the Python standard library.

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
- Product data extraction
- Price tracking
- Price history management
- SQLite database management
- CRUD operations
- File exporting
- CSV generation
- JSON generation
- CustomTkinter GUI development
- Exception handling
- Logging
- Modular application architecture
- Object-Oriented Programming

---

# 🔄 Application Workflow

```text
Enter Product URL
        ↓
Fetch Webpage
        ↓
Parse HTML
        ↓
Extract Product Information
        ↓
Store Product
        ↓
Set Target Price
        ↓
Record Price
        ↓
Display Results
        ↓
View Price History
        ↓
Export CSV / JSON
```

---

# 🚀 Future Improvements

- Support for more shopping websites
- Site-specific parsers
- Automated price checking
- Scheduled price tracking
- Email notifications
- Desktop notifications
- Telegram notifications
- Price history charts
- Product image extraction
- Duplicate product detection
- Product search
- Price-drop notifications
- Multiple currency support
- Currency conversion
- Database backup
- More export formats
- API support
- Automated testing

---

# 👨‍💻 Author

**Devender J**

Data Analyst | Python Developer | AI & Machine Learning Enthusiast

GitHub: https://github.com/JDevender007

---

<div align="center">

⭐ Python Web Scraping Project

</div>
# 🛒 Amazon Price Tracker

### A Python desktop application for tracking product prices, monitoring target prices, viewing price history, and managing tracked products through a modern dashboard.

---

# 📖 About

Amazon Price Tracker is a Python desktop application designed to monitor product prices from supported product websites.

The application accepts a product URL, retrieves available product information, extracts the product name and current price, stores product details, records price history, and compares the current price with a user-defined target price.

The project uses a modular architecture with separate components for scraping, parsing, tracking, database management, exporting, configuration, logging, utilities, controls, and the graphical interface.

---

# ✨ Features

- Enter product URL
- Fetch product information
- Extract product name
- Extract current price
- Extract product availability
- Set target price
- Track current price
- Track lowest recorded price
- Record price history
- Calculate price changes
- Monitor target prices
- Display tracked products
- View price history
- Delete tracked products
- Export data to CSV
- Export data to JSON
- SQLite database storage
- Request timeout handling
- HTTP error handling
- Activity logging
- Modern dark dashboard
- Status indicators
- Fullscreen mode
- Keyboard shortcuts
- Modular project architecture

---

# 🛠 Technologies

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
├── logs/
├── exports/
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

The application is designed for supported product websites.

Example:

```text
https://www.amazon.in/
```

Other websites might use different HTML structures or restrict automated requests.

A website returning HTTP 403 means the server refused the request. This does not indicate a Python installation problem.

---

# 🔎 Price Tracking

The application allows you to define a target price for each tracked product.

Example:

```text
Current Price: ₹45,999
Target Price:  ₹40,000
```

The application compares the current price with the target price.

When:

```text
Current Price <= Target Price
```

the product receives a target-price status.

The application also stores the lowest recorded price for each product.

---

# 📈 Price History

Each successful price check is stored in the SQLite database.

The history contains:

```text
price
checked_at
product_id
```

This allows the application to maintain historical price records for tracked products.

---

# 📤 Export

### CSV

The CSV export contains:

```text
name
url
current_price
target_price
lowest_price
availability
last_checked
created_at
```

### JSON

The JSON export stores the same product information in structured JSON format.

---

# 🗄️ Database

The application uses SQLite for local data storage.

### Products

```text
id
name
url
current_price
target_price
lowest_price
availability
last_checked
created_at
```

### Price History

```text
id
product_id
price
checked_at
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl + R | Refresh Data |
| Ctrl + N | Add Product |
| Ctrl + P | Open Products |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |

---

# 🔄 Application Workflow

```text
Enter Product URL
        ↓
Validate URL
        ↓
Fetch Webpage
        ↓
Parse HTML
        ↓
Extract Product Information
        ↓
Store Product
        ↓
Record Price
        ↓
Compare Target Price
        ↓
Display Dashboard
        ↓
View Price History
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
- Product data extraction
- Price tracking
- Price history management
- SQLite database management
- CRUD operations
- CSV generation
- JSON generation
- CustomTkinter GUI development
- Exception handling
- Logging
- Modular application architecture
- Object-Oriented Programming
- UI/UX design principles

---

# 🚀 Future Improvements

- Automated scheduled price checks
- Email notifications
- Telegram notifications
- Desktop notifications
- Price history charts
- Multiple marketplace support
- Site-specific parsers
- Product image extraction
- Duplicate product detection
- Product search
- Price-drop percentage alerts
- Background monitoring
- Currency conversion
- Multiple currency support
- Database backup
- Automated testing
- API integration

---

# 👨‍💻 Author

**Devender J**

Data Analyst | Python Developer | AI & Machine Learning Enthusiast

GitHub: https://github.com/JDevender007

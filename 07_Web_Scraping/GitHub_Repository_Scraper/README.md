<div align="center">

# 🐙 GitHub Repository Scraper

### A Python desktop application for scraping GitHub repositories from trending pages or user profiles with detailed information, stars, forks, and export capabilities.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-HTML%20Parser-success?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

GitHub Repository Scraper is a Python desktop application designed to collect repository information from GitHub.

The application supports two modes:
- **Trending**: Scrape GitHub trending repositories with optional language filter and time period (daily, weekly, monthly)
- **User**: Scrape all public repositories for a specific GitHub user

For each repository, it extracts name, owner, description, language, stars, forks, and more. Detailed scraping fetches topics, license, last commit, releases, watchers, issues, pull requests, and README preview. Data can be exported to CSV or JSON format.

The project follows a modular architecture with separate components for scraping, parsing, tracking, exporting, configuration, logging, and the graphical interface.

---

# ✨ Features

- **Two Scraping Modes**:
  - Trending repositories (with language filter: Python, JavaScript, Go, Rust, etc.)
  - User repositories (by GitHub username)
- **Time Periods**: Daily, Weekly, Monthly trending
- **Extract Repository Data**:
  - Name, Owner, Full Name
  - Description
  - Primary Language (with color)
  - Stars, Forks, Today's Stars (trending)
  - Contributors (trending)
- **Detailed Scraping**:
  - Topics/Tags
  - License
  - Last Commit Date
  - Releases
  - Watchers Count
  - Open Issues
  - Pull Requests
  - README Preview
- **Display & Interaction**:
  - Sortable table with GitHub-style dark theme
  - Double-click for detailed view
  - Progress indicator
- **Export**:
  - CSV with all fields
  - JSON with metadata
- **Rate Limiting**: Polite scraping with delays
- **Error Handling**: Timeouts, HTTP errors, parsing errors
- **Logging**: File and console logging
- **Keyboard Shortcuts**

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter (GUI with GitHub-inspired dark theme)
- Requests (HTTP)
- BeautifulSoup4 (HTML Parsing)
- lxml (Parser backend)
- CSV / JSON (Export)
- Logging
- Threading (Non-blocking GUI)

---

# 📂 Project Structure

```text
GitHub_Repository_Scraper/
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
│   ├── colors.py           # GitHub dark theme colors
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

# 🌐 Target Websites

The application scrapes:
- **Trending**: `https://github.com/trending` (with optional `/language?since=period`)
- **User Repos**: `https://github.com/username?tab=repositories`
- **Repo Details**: Individual repository pages

**Note:** GitHub may rate-limit or block automated requests. The application includes rate limiting (2s delay) and proper headers, but extraction results depend on GitHub's current HTML structure.

---

# 📊 Data Fields

## Trending Mode (Basic)
- Rank
- Name, Owner, Full Name
- URL
- Description
- Language (with color)
- Stars, Forks, Today's Stars
- Contributors

## User Mode (Basic)
- Rank
- Name, Owner
- URL
- Description
- Language
- Stars, Forks
- Last Updated

## Detailed Data (Both Modes)
- Topics/Tags
- License
- Last Commit
- Releases
- Watchers
- Open Issues
- Pull Requests
- README Preview

---

# 📤 Export

### CSV
Exports all fields with list values joined by semicolons.

### JSON
Exports structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "total_repos": 25,
  "repos": [...]
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + S | Scrape Repositories |
| Ctrl + D | Scrape Details |
| Ctrl + E | Export Data |
| F11 | Toggle Fullscreen |
| Escape | Exit Fullscreen |
| Double-click / Enter | View Repository Details |

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
- GitHub HTML structure analysis
- Data cleaning and normalization
- Rate limiting and polite scraping
- Threading for responsive GUI
- Tkinter GUI development with custom theme
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
Select Mode (Trending/User)
        ↓
Enter Language/Username
        ↓
Select Time Period (Trending)
        ↓
Fetch Page
        ↓
Parse Repository List
        ↓
Display in Table
        ↓
Select Repositories (optional)
        ↓
Scrape Details
        ↓
Export CSV / JSON
```

---

# 🚀 Future Improvements

- Repository search by keywords
- Filter by stars/forks/language
- Pagination support for user repos
- Organization repositories
- Repository comparison
- Language statistics visualization
- Star history charts
- Contributor activity
- Dependency analysis
- Security advisories
- Database storage (SQLite)
- Scheduled scraping
- GitHub API integration (with token)
- More export formats (Excel, Markdown)
- Theme customization
- Column visibility toggles

---

# ⚠️ Legal & Ethical Notice

This project is for educational purposes only. Please respect GitHub's Terms of Service and robots.txt.

- Use rate limiting (built-in 2 second delay)
- Do not scrape excessively
- Consider using GitHub's official API for production use
- This tool scrapes publicly available data only
- Respect user privacy and repository licenses

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python Web Scraping Project

</div>
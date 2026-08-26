<div align="center">

# 🐙 GitHub Profile Analyzer

### A Python desktop application for comprehensive GitHub profile analysis using the GitHub REST API with modern GUI, statistics, and export capabilities.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-HTTP-blue?style=for-the-badge)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-orange?style=for-the-badge)
![GitHub API](https://img.shields.io/badge/GitHub_REST_API-181717?style=for-the-badge&logo=github&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

GitHub Profile Analyzer is a Python desktop application that provides comprehensive analysis of GitHub user profiles using the GitHub REST API.

The application fetches and displays:
- **User Profile**: Avatar, bio, company, location, social links, account age
- **Repository Analysis**: All public repositories with stars, forks, languages, topics
- **Language Statistics**: Visual breakdown of programming languages used
- **Activity Feed**: Recent events (pushes, issues, PRs, releases, stars, forks)
- **Social Graph**: Followers and following lists
- **Rate Limit Monitoring**: Real-time API rate limit status

Features a GitHub-inspired dark theme, comprehensive export options (CSV/JSON), and token support for higher rate limits.

---

# ✨ Features

- **Profile Overview**: Complete user profile with stats cards
- **Repository Browser**: Sortable, filterable repository list with detailed cards
- **Language Analytics**: Visual language distribution bars with percentages
- **Activity Timeline**: Recent events with rich payload details
- **Social Networks**: Followers and following with profiles
- **Export System**: CSV/JSON export for profiles, repos, stats, events
- **GitHub Token Support**: Personal access token for 5000 req/hr (vs 60/hr)
- **Rate Limit Monitor**: Real-time API quota display
- **Caching**: 5-minute cache to minimize API calls
- **Modern Dark Theme**: GitHub-style UI with color-coded languages
- **Keyboard Shortcuts**: Efficient workflow

---

# 🛠 Technologies Used

- Python 3.13
- Tkinter (GUI with GitHub-inspired dark theme)
- Requests (HTTP client with retry logic)
- python-dotenv (environment variables)
- CSV / JSON (data export)
- Logging
- Threading (non-blocking GUI)
- Type hints
- Dataclasses
- GitHub REST API v3

---

# 📂 Project Structure

```text
03_GitHub_Profile_Analyzer/
│
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── api_client.py       # GitHub REST API client
│   ├── models.py           # Data models (dataclasses)
│   ├── tracker.py          # Data fetching coordination
│   ├── exporter.py         # CSV/JSON export
│   ├── logger.py           # Logging setup
│   ├── utils.py            # Utility functions
│   ├── colors.py           # GitHub dark theme colors
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

# 🔑 GitHub Token Setup (Optional but Recommended)

1. Go to [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Generate a new token (classic) with `public_repo` scope
3. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
4. Edit `.env` and add your token:
   ```
   GITHUB_TOKEN=ghp_your_token_here
   ```

**Benefits of using a token:**
- 5,000 requests/hour (vs 60/hour without token)
- Access to private repos (if you own them)
- Higher search rate limits

---

# ▶️ Run

Run the application from the project root:

```bash
python -m src.app
```

---

# 🌐 API Endpoints Used

- **User Profile**: `GET /users/{username}`
- **User Repositories**: `GET /users/{username}/repos` (paginated)
- **Repository Details**: `GET /repos/{owner}/{repo}`
- **Repository Languages**: `GET /repos/{owner}/{repo}/languages`
- **Repository Contributors**: `GET /repos/{owner}/{repo}/contributors`
- **User Events**: `GET /users/{username}/events/public`
- **User Followers**: `GET /users/{username}/followers`
- **User Following**: `GET /users/{username}/following`
- **Rate Limit**: `GET /rate_limit`

---

# 📊 Data Displayed

## Profile
- Avatar, name, username, bio
- Company, blog, location, email
- Twitter, public repos, gists
- Followers, following, account age

## Repositories
- Name, description, language (with color)
- Stars, forks, watchers, size
- Created/updated/pushed dates
- Fork/archived/private status
- License, topics, URL

## Language Statistics
- Language name with official color
- Repository count and percentage
- Visual progress bars

## Activity Events
- PushEvent (with commit messages)
- IssuesEvent (action + title)
- PullRequestEvent (action + title)
- WatchEvent, ForkEvent, ReleaseEvent
- CreateEvent, DeleteEvent

## Social
- Followers list with profiles
- Following list with profiles

---

# 📤 Export

### CSV
Structured tabular data for spreadsheet analysis.

### JSON
Structured data with metadata:
```json
{
  "exported_at": "2024-01-15T10:30:00",
  "profile": {
    "login": "octocat",
    "name": "The Octocat",
    "followers": 9000,
    ...
  }
}
```

---

# ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + F | Focus username entry |
| Ctrl + R | Refresh data |
| Ctrl + E | Export profile |
| F11 | Toggle fullscreen |
| Escape | Exit fullscreen |
| Enter | Analyze (in username field) |

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

- GitHub REST API v3 consumption
- Pagination handling with Link headers
- Rate limit management and monitoring
- Personal access token authentication
- Dataclass-based data modeling
- Threading for responsive GUI during API calls
- Tkinter custom widget development (StatCard, LanguageBar, RepoCard, EventCard)
- GitHub-inspired dark theme with language colors
- CSV/JSON data export with metadata
- Exponential backoff retry strategy
- Response caching with TTL
- Rich event payload parsing
- Language color coding
- Modular application architecture
- Type hints and comprehensive documentation

---

# 🔄 Application Workflow

```text
Enter GitHub Username
         ↓
    Fetch User Profile
         ↓
    Fetch All Repositories (paginated)
         ↓
    Calculate Statistics
         ↓
    Display in Tabs (Overview, Repos, Languages, Activity)
         ↓
    Optional: Fetch Events, Followers, Following
         ↓
    Export Data (CSV/JSON)
```

---

# 🚀 Future Improvements

- Repository search by keywords
- Contribution graph visualization
- Starred repositories analysis
- Organization profile analysis
- Repository comparison tool
- Language trends over time
- Dependency analysis
- Security advisory scanning
- GitHub Actions workflow status
- Pull request analytics
- Issue tracking dashboard
- Export to PDF reports
- Multi-user comparison
- Web-based version (FastAPI + React)
- Docker containerization
- CI/CD pipeline

---

# ⚠️ API Limitations

**Without Token**: 60 requests/hour per IP
**With Token**: 5,000 requests/hour per user

**Pagination**: Max 100 items per page
**Search**: Not implemented (would require different endpoints)

The app implements:
- Automatic pagination for repositories
- 5-minute response caching
- Rate limit monitoring
- Exponential backoff on errors
- Graceful degradation when rate limited

---

# 👨‍💻 Author

**Devender J**

Data Analyst • Python Developer • AI & Machine Learning Enthusiast

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ Python API Development Project

</div>
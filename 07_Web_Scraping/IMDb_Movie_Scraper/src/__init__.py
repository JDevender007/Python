"""
IMDb Movie Scraper - Package Initialization
"""

__version__ = "1.0.0"
__author__ = "Devender J"
__description__ = "A Python desktop application for scraping movie data from IMDb"

from .config import *
from .scraper import *
from .parser import *
from .tracker import *
from .exporter import *
from .logger import *
from .utils import *
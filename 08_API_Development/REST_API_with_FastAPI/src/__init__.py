"""
REST API with FastAPI - Package Initialization
"""

__version__ = "1.0.0"
__author__ = "Devender J"
__description__ = "A complete REST API for task management built with FastAPI"

from .config import *
from .database import *
from .schemas import *
from .auth import *
from .crud import *
"""Run Platapicker backend server."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from backend.main import app

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    # Disable hot-reload when running inside the Electron app (PLATAPICKER_DATA_DIR is set)
    is_production = bool(os.getenv("PLATAPICKER_DATA_DIR"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=not is_production)

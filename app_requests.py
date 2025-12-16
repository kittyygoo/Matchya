"""
Compatibility shim to keep `streamlit run app_requests.py` working.
The full app now lives in `app.py` and the `matchya/` package.
"""

from app import *  # noqa: F401,F403

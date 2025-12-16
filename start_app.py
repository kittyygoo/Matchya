# start_app.py
import os, sys, subprocess, tempfile, shutil

def resource_path(relative_path: str) -> str:
    # Works for PyInstaller --onefile and normal execution
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    app_path = resource_path("app.py")
    # Some versions of Streamlit try to resolve relative paths; make them absolute
    app_abs = os.path.abspath(app_path)

    # Prefer opening default browser automatically
    args = [
        sys.executable, "-m", "streamlit", "run", app_abs,
        "--server.port=85948",
        "--server.address=0.0.0.0",
        "--browser.serverAddress=localhost",
        "--browser.gatherUsageStats=false",
        "--client.showErrorDetails=true",
    ]
    print("Launching Streamlit app...")
    print("If a browser doesn't open automatically, open http://localhost:85948")
    sys.exit(subprocess.call(args))

if __name__ == "__main__":
    main()

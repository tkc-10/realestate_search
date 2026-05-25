"""
起動スクリプト

使い方:
  1. pip install -r requirements.txt
  2. playwright install chromium
  3. python run.py

ブラウザが http://localhost:8000 で自動的に開きます。
"""
import subprocess
import sys
import webbrowser
import threading
import time


def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])

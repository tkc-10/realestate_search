"""
起動スクリプト

使い方:
  1. pip3 install -r requirements.txt   (Macは pip3、Windowsは pip)
  2. python3 run.py

ブラウザが http://localhost:8000 で自動的に開きます。
"""
import subprocess
import sys
import webbrowser
import threading
import time


def check_playwright():
    """Playwrightのブラウザが未インストールなら自動インストール"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception:
        print("Playwright Chromiumをインストールしています...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("インストール完了")


def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    check_playwright()
    threading.Thread(target=open_browser, daemon=True).start()
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])

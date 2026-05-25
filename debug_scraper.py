"""
スクレイパーデバッグツール

使い方:
  python3 debug_scraper.py <URL> [rakumachi|kenbiya]

例:
  python3 debug_scraper.py "https://www.rakumachi.jp/syuuekibukken/area/division/?ken=13&division=1" rakumachi
  python3 debug_scraper.py "https://www.kenbiya.com/ar/ns/tokyo/a_mansion/" kenbiya

取得したHTMLを debug_output.html に保存します。
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def debug_scrape(url: str, site: str = "rakumachi"):
    print(f"\n{'='*60}")
    print(f"対象URL: {url}")
    print(f"サイト: {site}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # ブラウザを表示して確認
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        page = context.new_page()

        print("ページを読み込み中...")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # HTMLを保存
        html = page.content()
        out_path = Path("debug_output.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"HTML保存: {out_path.resolve()} ({len(html):,} bytes)\n")

        # よく使われるセレクタを試してマッチ数を表示
        print("--- セレクタの一致数 ---")
        selectors_to_try = [
            # 楽待系
            "ul.bukken-list > li",
            "li.js-bukken-cassette",
            ".property-list-item",
            "[class*='bukken-cassette']",
            "[class*='bukken-list'] li",
            "[class*='property-list'] li",
            "[class*='cassette']",
            # 健美家系
            "table.re_table > tbody > tr",
            "tr.datarow",
            "tr[class*='data']",
            ".bukken_list li",
            "[class*='property-item']",
            # 汎用
            "article",
            "[itemtype*='Product']",
            "li[class]",
            "div[class*='item']",
            "div[class*='card']",
            "div[class*='list']",
        ]

        matched = []
        for sel in selectors_to_try:
            try:
                count = len(page.query_selector_all(sel))
                if count > 0:
                    matched.append((sel, count))
                    print(f"  ✓ {count:3d}件  {sel}")
            except Exception:
                pass

        if not matched:
            print("  マッチするセレクタが見つかりませんでした")
            print("\n  → ページがJavaScriptで動的に読み込まれているか、")
            print("    ボットブロックされている可能性があります。")
            print("    ブラウザウィンドウで実際のページを確認してください。")
        else:
            print(f"\n最も件数が多いセレクタ: '{max(matched, key=lambda x: x[1])[0]}'")
            print("\n--- 最も一致数が多いセレクタの最初の要素のHTML ---")
            best_sel = max(matched, key=lambda x: x[1])[0]
            first_el = page.query_selector(best_sel)
            if first_el:
                inner = first_el.inner_html()[:800]
                print(inner)

        print("\n--- ページタイトル ---")
        print(page.title())

        print("\n--- 物件リンク (href に物件IDっぽいものが含まれるもの上位10件) ---")
        links = page.query_selector_all("a[href]")
        prop_links = []
        for a in links:
            href = a.get_attribute("href") or ""
            # 物件ページらしいURLを抽出（数字IDを含むもの）
            import re
            if re.search(r'/\d{4,}', href) or 'bukken' in href or 'property' in href or '/ar/' in href:
                text = a.inner_text().strip()[:40]
                prop_links.append(f"  {href[:80]}  ({text})")
        for l in prop_links[:10]:
            print(l)
        if not prop_links:
            print("  物件リンクが見つかりませんでした")

        input("\n[Enter]でブラウザを閉じます...")
        browser.close()

    print("\ndebug_output.html をブラウザで開いてHTMLを確認してください。")
    print("その情報を元にCSSセレクタを更新できます。")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    site = sys.argv[2] if len(sys.argv) > 2 else "rakumachi"
    debug_scrape(url, site)

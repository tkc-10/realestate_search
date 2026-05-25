"""
スクレイパーデバッグツール

使い方:
  python3 debug_scraper.py <URL> [rakumachi|kenbiya]

例:
  python3 debug_scraper.py "https://www.rakumachi.jp/syuuekibukken/..." rakumachi
  python3 debug_scraper.py "https://www.kenbiya.com/ar/ns/tokyo/a_mansion/" kenbiya
"""
import sys
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def debug_scrape(url: str, site: str = "rakumachi"):
    print(f"\n{'='*60}")
    print(f"対象URL: {url}")
    print(f"サイト: {site}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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

        print(f"--- ページタイトル ---")
        print(page.title())

        # ========== 物件リンクを起点に親要素を調べる ==========
        print("\n\n========== 物件リンクの親要素を調査 ==========")

        if site == "rakumachi":
            prop_links = page.query_selector_all("a[href*='/syuuekibukken/'][href*='/show.html']")
        else:
            prop_links = page.query_selector_all("a[href*='/ar/'][href*='/']")

        print(f"物件リンク数: {len(prop_links)}")

        for i, link in enumerate(prop_links[:5]):
            href = link.get_attribute("href") or ""
            link_text = link.inner_text().strip()[:60]
            print(f"\n--- 物件{i+1}: {href} ---")
            print(f"  リンクテキスト: {link_text}")

            # 親要素を5段階さかのぼって調べる
            parent_info = link.evaluate("""el => {
                let result = [];
                let p = el.parentElement;
                for (let i = 0; i < 8; i++) {
                    if (!p || p.tagName === 'BODY') break;
                    result.push({
                        tag: p.tagName.toLowerCase(),
                        className: p.className.toString().trim().slice(0, 80),
                        childCount: p.children.length,
                        textLength: p.innerText.length
                    });
                    p = p.parentElement;
                }
                return result;
            }""")

            for j, info in enumerate(parent_info):
                print(f"  親{j+1}: <{info['tag']} class=\"{info['className']}\"> "
                      f"子要素:{info['childCount']} テキスト長:{info['textLength']}")

        # ========== 物件カードのHTML（最初の1件）==========
        print("\n\n========== 最初の物件カードのHTML ==========")
        if prop_links:
            card_html = prop_links[0].evaluate("""el => {
                // liまたはarticleの祖先を探す
                let p = el.parentElement;
                let maxUp = 8;
                while (p && maxUp-- > 0) {
                    if (p.tagName === 'LI' || p.tagName === 'ARTICLE') return p.outerHTML;
                    // クラス名にcassetteやitemやcardが含まれるdivも候補
                    let cls = p.className ? p.className.toString() : '';
                    if (p.tagName === 'DIV' && (
                        cls.includes('cassette') || cls.includes('item') ||
                        cls.includes('card') || cls.includes('bukken') ||
                        cls.includes('property')
                    )) return p.outerHTML;
                    p = p.parentElement;
                }
                return el.parentElement?.outerHTML || '';
            }""")
            # 最初の1000文字だけ表示
            print(card_html[:1500])

        # ========== テキスト全体から価格・利回りパターンを探す ==========
        print("\n\n========== 物件カードのテキスト情報 ==========")
        if prop_links:
            for i, link in enumerate(prop_links[:5]):
                card_text = link.evaluate("""el => {
                    let p = el.parentElement;
                    let maxUp = 8;
                    while (p && maxUp-- > 0) {
                        if (p.tagName === 'LI' || p.tagName === 'ARTICLE') return p.innerText;
                        let cls = p.className ? p.className.toString() : '';
                        if (p.tagName === 'DIV' && (
                            cls.includes('cassette') || cls.includes('item') ||
                            cls.includes('card') || cls.includes('bukken') ||
                            cls.includes('property')
                        )) return p.innerText;
                        p = p.parentElement;
                    }
                    return el.parentElement?.innerText || '';
                }""")
                href = link.get_attribute("href") or ""
                m = re.search(r'/dim(\d+)/(\d+)/show', href)
                print(f"\n物件{i+1} ID:{m.group(2) if m else '?'}  type:{m.group(1) if m else '?'}")
                # 改行ごとに表示
                for line in card_text.strip().split("\n"):
                    line = line.strip()
                    if line:
                        print(f"  | {line[:80]}")

        input("\n\n[Enter]でブラウザを閉じます...")
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    url = sys.argv[1]
    site = sys.argv[2] if len(sys.argv) > 2 else "rakumachi"
    debug_scrape(url, site)

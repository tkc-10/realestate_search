"""
楽待 (rakumachi.jp) スクレイパー

検索URL例:
  一棟アパート(東京): https://www.rakumachi.jp/syuuekibukken/area/division/?ken=13&division=1
  区分マンション:      https://www.rakumachi.jp/syuuekibukken/area/division/?ken=13&division=4

物件種別コード (divisionパラメータ):
  1=一棟アパート, 2=一棟マンション, 3=一棟ビル, 4=区分マンション, 5=戸建て, 6=土地, 7=その他
"""
import re
import time
import logging
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, PropertyData

logger = logging.getLogger(__name__)

BASE_URL = "https://www.rakumachi.jp"

PROPERTY_TYPE_MAP = {
    "1": "一棟アパート",
    "2": "一棟マンション",
    "3": "一棟ビル",
    "4": "区分マンション",
    "5": "戸建て",
    "6": "土地",
    "7": "その他",
}


def _add_page_param(url: str, page: int) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if page > 1:
        params["p"] = [str(page)]
    elif "p" in params:
        del params["p"]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


class RakumachiScraper(BaseScraper):
    def __init__(self):
        super().__init__("rakumachi")

    def scrape_search_page(self, url: str, page_num: int = 1) -> list[PropertyData]:
        target_url = _add_page_param(url, page_num)
        logger.info(f"[楽待] スクレイピング: {target_url}")

        properties = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36",
                locale="ja-JP",
            )
            page = context.new_page()
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                # 物件カードを取得 (セレクタは実際のHTML構造に合わせて調整が必要)
                cards = page.query_selector_all("ul.bukken-list > li, .property-list-item, li.js-bukken-cassette")
                if not cards:
                    # 汎用フォールバック
                    cards = page.query_selector_all("[class*='bukken']")

                logger.info(f"[楽待] 物件カード数: {len(cards)}")

                for card in cards:
                    try:
                        prop = _parse_card(card, page)
                        if prop:
                            properties.append(prop)
                    except Exception as e:
                        logger.warning(f"[楽待] カードパースエラー: {e}")

                # 次ページが存在しない場合は空リストを返す
                if page_num > 1 and not properties:
                    pass

            except PlaywrightTimeout:
                logger.error(f"[楽待] タイムアウト: {target_url}")
            except Exception as e:
                logger.error(f"[楽待] エラー: {e}")
            finally:
                browser.close()

        return properties


def _parse_card(card, page) -> PropertyData | None:
    """物件カードからデータを抽出"""
    # リンク取得
    link_el = card.query_selector("a[href*='/syuuekibukken/']")
    if not link_el:
        link_el = card.query_selector("a")
    if not link_el:
        return None

    href = link_el.get_attribute("href") or ""
    if not href:
        return None
    url = href if href.startswith("http") else urljoin(BASE_URL, href)

    # 物件IDをURLから抽出
    m = re.search(r"[?&]id=(\d+)", url) or re.search(r"/(\d+)/?$", url)
    external_id = m.group(1) if m else url

    # タイトル
    title_el = (
        card.query_selector(".bukken-cassette-title, .property-title, h3, h2")
    )
    title = title_el.inner_text().strip() if title_el else None

    # 価格
    price_el = card.query_selector(
        ".price, .bukken-price, [class*='price'], .cassette-price"
    )
    price_text = price_el.inner_text().strip() if price_el else ""
    price = BaseScraper.parse_price(price_text)

    # 利回り
    yield_el = card.query_selector(
        ".rimawari, .yield, [class*='yield'], [class*='rimawari']"
    )
    yield_text = yield_el.inner_text().strip() if yield_el else ""
    gross_yield = BaseScraper.parse_yield(yield_text)

    # 所在地
    location_el = card.query_selector(
        ".address, .location, [class*='address'], [class*='location']"
    )
    location = location_el.inner_text().strip() if location_el else None
    prefecture = _extract_prefecture(location or "")

    # 物件種別
    type_el = card.query_selector("[class*='type'], [class*='bukken-type']")
    property_type = type_el.inner_text().strip() if type_el else None

    # 築年数
    age_el = card.query_selector("[class*='age'], [class*='chikunen']")
    age_text = age_el.inner_text().strip() if age_el else ""
    building_age = BaseScraper.parse_age(age_text)

    # 面積
    area_el = card.query_selector("[class*='area'], [class*='menseki']")
    area_text = area_el.inner_text().strip() if area_el else ""
    building_area = BaseScraper.parse_area(area_text)

    # 画像
    img_el = card.query_selector("img")
    image_url = img_el.get_attribute("src") if img_el else None
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url

    return PropertyData(
        external_id=external_id,
        url=url,
        title=title,
        price=price,
        price_text=price_text or None,
        location=location,
        prefecture=prefecture or None,
        property_type=property_type,
        gross_yield=gross_yield,
        building_age=building_age,
        building_area=building_area,
        image_url=image_url,
    )


def _extract_prefecture(location: str) -> str:
    prefectures = [
        "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
        "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川",
        "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜",
        "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫",
        "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口",
        "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎",
        "熊本", "大分", "宮崎", "鹿児島", "沖縄",
    ]
    for pref in prefectures:
        if pref in location:
            return pref
    return ""

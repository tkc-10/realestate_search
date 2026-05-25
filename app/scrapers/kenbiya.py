"""
健美家 (kenbiya.com) スクレイパー

検索URL例:
  一棟アパート(東京): https://www.kenbiya.com/ar/ns/tokyo/a_mansion/
  区分マンション:      https://www.kenbiya.com/ar/ns/tokyo/ms/
  戸建て:             https://www.kenbiya.com/ar/ns/tokyo/house/

物件種別パス:
  a_mansion=一棟アパート, mansion=一棟マンション, office=一棟ビル,
  ms=区分マンション, house=戸建て, land=土地
"""
import re
import time
import logging
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, PropertyData

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kenbiya.com"


def _add_page_param(url: str, page: int) -> str:
    """健美家はURLパスでページネーション: .../pXX/ の形式"""
    url = url.rstrip("/")
    # 既存のページパラメータを削除
    url = re.sub(r"/p\d+$", "", url)
    if page > 1:
        url = f"{url}/p{page}"
    return url + "/"


class KenbiyaScraper(BaseScraper):
    def __init__(self):
        super().__init__("kenbiya")

    def scrape_search_page(self, url: str, page_num: int = 1) -> list[PropertyData]:
        target_url = _add_page_param(url, page_num)
        logger.info(f"[健美家] スクレイピング: {target_url}")

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

                # 物件リスト取得
                cards = page.query_selector_all(
                    "table.re_table > tbody > tr, "
                    ".bukken_list li, "
                    "[class*='property-item'], "
                    "tr.datarow"
                )
                if not cards:
                    cards = page.query_selector_all("tr[class*='data']")

                logger.info(f"[健美家] 物件カード数: {len(cards)}")

                for card in cards:
                    try:
                        prop = _parse_card(card)
                        if prop:
                            properties.append(prop)
                    except Exception as e:
                        logger.warning(f"[健美家] カードパースエラー: {e}")

            except PlaywrightTimeout:
                logger.error(f"[健美家] タイムアウト: {target_url}")
            except Exception as e:
                logger.error(f"[健美家] エラー: {e}")
            finally:
                browser.close()

        return properties


def _parse_card(card) -> PropertyData | None:
    # リンク取得
    link_el = card.query_selector("a[href*='/ar/'], a[href*='/bukken/']")
    if not link_el:
        link_el = card.query_selector("a")
    if not link_el:
        return None

    href = link_el.get_attribute("href") or ""
    if not href:
        return None
    url = href if href.startswith("http") else urljoin(BASE_URL, href)

    # 物件IDをURLから抽出
    m = re.search(r"/(\d+)/?(?:\?|$)", url)
    external_id = m.group(1) if m else url

    # タイトル
    title_el = (
        card.query_selector(".property_title, h3, .bukken_title, td.title")
    )
    title = title_el.inner_text().strip() if title_el else None

    # 価格
    price_el = card.query_selector(
        ".price, td.price, [class*='price'], .kakaku"
    )
    price_text = price_el.inner_text().strip() if price_el else ""
    price = BaseScraper.parse_price(price_text)

    # 利回り
    yield_el = card.query_selector(
        ".rimawari, td.rimawari, [class*='yield'], [class*='rimawari']"
    )
    yield_text = yield_el.inner_text().strip() if yield_el else ""
    gross_yield = BaseScraper.parse_yield(yield_text)

    # 所在地
    location_el = card.query_selector(
        ".address, td.address, [class*='address'], .location, td.area"
    )
    location = location_el.inner_text().strip() if location_el else None
    prefecture = _extract_prefecture(location or "")

    # 物件種別
    type_el = card.query_selector("[class*='type'], td.type, .bukken_type")
    property_type = type_el.inner_text().strip() if type_el else None

    # 築年数
    age_el = card.query_selector("[class*='age'], td.age, [class*='chikunen']")
    age_text = age_el.inner_text().strip() if age_el else ""
    building_age = BaseScraper.parse_age(age_text)

    # 建物面積
    area_el = card.query_selector("[class*='area'], td.area, [class*='menseki']")
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

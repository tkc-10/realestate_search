"""
楽待 (rakumachi.jp) スクレイパー

物件カード構造:
  div.propertyBlock
    p.propertyBlock__dimension  → 物件種別 (例: 戸建賃貸、1棟マンション)
    p.propertyBlock__name       → 物件名(所在地)
    p.propertyBlock__update     → 登録日
    a.propertyBlock__content    → 物件詳細リンク (href に /dimXXXX/YYYYYYY/show.html)

カードテキストのラベル→値パターン:
  価格 → 650万円
  利回り → 11.07%
  所在地 → 大阪府堺市...
  交通 → 南海高野線 北野田駅 徒歩27分
  築年月 → 1979年07月（築47年）
  総戸数 → 14戸
  面積 → 建物76.95㎡ / 土地 61.03㎡

ページネーション: ?page=2, ?page=3 ...
"""
import re
import time
import logging
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, PropertyData

logger = logging.getLogger(__name__)

BASE_URL = "https://www.rakumachi.jp"

DIM_TYPE_MAP = {
    "1001": "一棟マンション",
    "1002": "一棟アパート",
    "1003": "一棟ビル",
    "1004": "戸建賃貸",
    "2001": "区分マンション",
    "2002": "区分所有ビル",
    "3001": "土地",
}

KNOWN_LABELS = {
    "価格", "利回り", "所在地", "交通", "築年月",
    "総戸数", "建物構造", "面積", "階数",
}


def _add_page_param(url: str, page: int) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if page > 1:
        params["page"] = [str(page)]
    elif "page" in params:
        del params["page"]
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
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ja-JP",
            )
            page = context.new_page()
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)

                cards = page.query_selector_all("div.propertyBlock")
                logger.info(f"[楽待] 物件カード数: {len(cards)}")

                for card in cards:
                    try:
                        prop = _parse_card(card)
                        if prop:
                            properties.append(prop)
                    except Exception as e:
                        logger.warning(f"[楽待] カードパースエラー: {e}")

            except PlaywrightTimeout:
                logger.error(f"[楽待] タイムアウト: {target_url}")
            except Exception as e:
                logger.error(f"[楽待] エラー: {e}")
            finally:
                browser.close()

        return properties


def _parse_card(card) -> PropertyData | None:
    # 物件リンク取得
    link_el = card.query_selector("a.propertyBlock__content")
    if not link_el:
        return None

    href = link_el.get_attribute("href") or ""
    m = re.search(r"/dim(\d+)/(\d+)/show\.html", href)
    if not m:
        return None

    dim_code = m.group(1)
    external_id = m.group(2)
    prop_url = href if href.startswith("http") else urljoin(BASE_URL, href)

    # 物件種別
    type_el = card.query_selector("p.propertyBlock__dimension")
    property_type = type_el.inner_text().strip() if type_el else DIM_TYPE_MAP.get(dim_code)

    # 物件名
    name_el = card.query_selector("p.propertyBlock__name")
    name = name_el.inner_text().strip() if name_el else None
    title = f"{property_type} {name}".strip() if (property_type and name) else (name or property_type)

    # カードテキストをラベル→値パターンで解析
    card_text = card.inner_text()
    lines = [l.strip() for l in card_text.split("\n") if l.strip()]

    price_text = _get_label_value(lines, "価格")
    price = BaseScraper.parse_price(price_text or "")

    yield_text = _get_label_value(lines, "利回り")
    gross_yield = BaseScraper.parse_yield(yield_text or "")

    location = _get_label_value(lines, "所在地")
    prefecture = _extract_prefecture(location or "")

    station = _get_label_value(lines, "交通")

    age_text = _get_label_value(lines, "築年月")  # 例: "1979年07月（築47年）"
    building_age = _parse_building_age(age_text or "")

    units_text = _get_label_value(lines, "総戸数")  # 例: "14戸"
    total_units = None
    if units_text:
        mu = re.search(r"(\d+)", units_text)
        if mu:
            total_units = int(mu.group(1))

    area_text = _get_label_value(lines, "面積")  # 例: "建物266.61㎡ / 土地 215.92㎡"
    building_area = _parse_building_area(area_text or "")
    land_area = _parse_land_area(area_text or "")

    # 画像
    img_el = card.query_selector("img")
    image_url = None
    if img_el:
        src = img_el.get_attribute("src") or ""
        if src.startswith("//"):
            src = "https:" + src
        image_url = src or None

    return PropertyData(
        external_id=external_id,
        url=prop_url,
        title=title,
        price=price,
        price_text=price_text,
        location=location,
        prefecture=prefecture or None,
        property_type=property_type,
        gross_yield=gross_yield,
        building_age=building_age,
        building_area=building_area,
        land_area=land_area,
        total_units=total_units,
        station=station,
        image_url=image_url,
    )


def _get_label_value(lines: list[str], label: str) -> str | None:
    """行リストからラベルの次の行を値として取得"""
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line not in KNOWN_LABELS:
                return next_line
    return None


def _parse_building_age(text: str) -> int | None:
    # "1979年07月（築47年）" → 47
    m = re.search(r"築(\d+)年", text)
    return int(m.group(1)) if m else None


def _parse_building_area(area_text: str) -> float | None:
    # "建物266.61㎡ / 土地 215.92㎡" または "専有 57.35㎡"
    m = re.search(r"建物\s*(\d+(?:\.\d+)?)", area_text)
    if m:
        return float(m.group(1))
    m = re.search(r"専有\s*(\d+(?:\.\d+)?)", area_text)
    if m:
        return float(m.group(1))
    return None


def _parse_land_area(area_text: str) -> float | None:
    m = re.search(r"土地\s*(\d+(?:\.\d+)?)", area_text)
    return float(m.group(1)) if m else None


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

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PropertyData:
    external_id: str
    url: str
    title: Optional[str] = None
    price: Optional[int] = None
    price_text: Optional[str] = None
    location: Optional[str] = None
    prefecture: Optional[str] = None
    property_type: Optional[str] = None
    gross_yield: Optional[float] = None
    building_age: Optional[int] = None
    building_area: Optional[float] = None
    land_area: Optional[float] = None
    total_units: Optional[int] = None
    station: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class BaseScraper:
    def __init__(self, site_name: str):
        self.site_name = site_name

    def scrape_search_page(self, url: str, page_num: int = 1) -> list[PropertyData]:
        raise NotImplementedError

    def scrape_all_pages(self, base_url: str, max_pages: int = 5) -> list[PropertyData]:
        all_props: list[PropertyData] = []
        seen_ids: set[str] = set()

        for page in range(1, max_pages + 1):
            props = self.scrape_search_page(base_url, page)
            if not props:
                break
            new_props = [p for p in props if p.external_id not in seen_ids]
            if not new_props:
                break
            for p in new_props:
                seen_ids.add(p.external_id)
            all_props.extend(new_props)

        return all_props

    @staticmethod
    def parse_price(text: str) -> Optional[int]:
        """価格テキストを万円単位の整数に変換"""
        import re
        text = text.replace(",", "").replace(" ", "").strip()
        m = re.search(r"(\d+(?:\.\d+)?)億", text)
        if m:
            oku = float(m.group(1))
            rest_m = re.search(r"億.*?(\d+)万", text)
            man = int(rest_m.group(1)) if rest_m else 0
            return int(oku * 10000) + man
        m = re.search(r"(\d+)万", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def parse_yield(text: str) -> Optional[float]:
        """利回りテキストをfloatに変換"""
        import re
        m = re.search(r"(\d+(?:\.\d+)?)%", text)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def parse_area(text: str) -> Optional[float]:
        """面積テキストをm2のfloatに変換"""
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*m", text, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def parse_age(text: str) -> Optional[int]:
        """築年数テキストを整数に変換"""
        import re
        m = re.search(r"築(\d+)年", text)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d{4})年", text)
        if m:
            from datetime import datetime
            built = int(m.group(1))
            return datetime.now().year - built
        return None

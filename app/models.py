from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from .database import Base


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    search_configs = relationship("SearchConfig", back_populates="site")
    properties = relationship("Property", back_populates="site")


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    name = Column(String, nullable=False)
    search_url = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    interval_hours = Column(Integer, default=6)
    max_pages = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)

    site = relationship("Site", back_populates="search_configs")
    scrape_runs = relationship("ScrapeRun", back_populates="search_config")
    properties = relationship("Property", back_populates="search_config")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    search_config_id = Column(Integer, ForeignKey("search_configs.id"), nullable=True)
    external_id = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    price_text = Column(String, nullable=True)
    location = Column(String, nullable=True)
    prefecture = Column(String, nullable=True)
    property_type = Column(String, nullable=True)
    gross_yield = Column(Float, nullable=True)
    building_age = Column(Integer, nullable=True)
    building_area = Column(Float, nullable=True)
    land_area = Column(Float, nullable=True)
    total_units = Column(Integer, nullable=True)
    station = Column(String, nullable=True)
    image_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")  # active, delisted
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    delisted_at = Column(DateTime, nullable=True)
    days_listed = Column(Integer, nullable=True)

    site = relationship("Site", back_populates="properties")
    search_config = relationship("SearchConfig", back_populates="properties")
    history = relationship("PropertyHistory", back_populates="property", order_by="PropertyHistory.checked_at")


class PropertyHistory(Base):
    __tablename__ = "property_history"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    checked_at = Column(DateTime, default=datetime.utcnow)
    price = Column(Integer, nullable=True)
    gross_yield = Column(Float, nullable=True)
    status = Column(String, nullable=False)

    property = relationship("Property", back_populates="history")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    search_config_id = Column(Integer, ForeignKey("search_configs.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running, success, error
    properties_found = Column(Integer, default=0)
    properties_new = Column(Integer, default=0)
    properties_delisted = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    search_config = relationship("SearchConfig", back_populates="scrape_runs")

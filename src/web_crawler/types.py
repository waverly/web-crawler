from typing import TypedDict, List, Optional
from datetime import datetime
from pydantic import BaseModel


# TypedDicts for internal use
class Link(TypedDict):
    url: str
    title: str
    relevancy: float
    relevancy_explanation: str
    high_priority_keywords: List[str]
    medium_priority_keywords: List[str]
    context: str


class CrawlResult(TypedDict):
    url: str
    num_links: int
    links: List[Link]


# Pydantic models for API responses
class PageResponse(BaseModel):
    id: int
    url: str
    title: Optional[str]
    crawled_at: datetime

    class Config:
        from_attributes = True


class LinkResponse(BaseModel):
    url: str
    title: Optional[str]
    link_text: Optional[str]
    relevancy: float
    relevancy_explanation: str
    high_priority_keywords: List[str]
    medium_priority_keywords: List[str]

    class Config:
        from_attributes = True


class PageLinksResponse(BaseModel):
    page_id: int
    url: str
    links: List[LinkResponse]


class SearchResponse(BaseModel):
    links: List[LinkResponse]
    total: int

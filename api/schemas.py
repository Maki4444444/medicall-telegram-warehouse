"""
api/schemas.py
Pydantic request/response models for all FastAPI endpoints.
Every endpoint has a typed response model so FastAPI validates
and documents the output automatically via OpenAPI.
"""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="API status — always 'ok' if reachable.")
    database: str = Field(..., description="'connected' or 'unreachable'.")


class TopProduct(BaseModel):
    term: str = Field(..., description="Frequently mentioned term or product name.")
    mention_count: int = Field(..., description="Number of messages containing this term.")

    class Config:
        from_attributes = True


class ChannelActivityPoint(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format.")
    post_count: int = Field(..., description="Number of posts published on this date.")
    avg_views: float = Field(..., description="Average view count for posts on this date.")

    class Config:
        from_attributes = True


class ChannelActivityResponse(BaseModel):
    channel_name: str = Field(..., description="Telegram channel username.")
    total_posts: int = Field(..., description="Total scraped posts for this channel.")
    avg_views: float = Field(..., description="Overall average view count.")
    activity: list[ChannelActivityPoint] = Field(
        ..., description="Daily breakdown of posting activity."
    )


class MessageSearchResult(BaseModel):
    message_id: int = Field(..., description="Unique Telegram message ID.")
    channel_name: str = Field(..., description="Source channel username.")
    date: str = Field(..., description="Date the message was posted (YYYY-MM-DD).")
    message_text: str = Field(..., description="Full text content of the message.")
    view_count: int = Field(..., description="Number of views at time of scrape.")
    forward_count: int = Field(..., description="Number of forwards at time of scrape.")
    has_image: bool = Field(..., description="Whether the message had a downloaded image.")

    class Config:
        from_attributes = True


class VisualContentStat(BaseModel):
    channel_name: str = Field(..., description="Source channel username.")
    image_category: Optional[str] = Field(
        None,
        description="YOLO classification: promotional, product_display, lifestyle, or other.",
    )
    count: int = Field(..., description="Number of images in this category for this channel.")
    avg_confidence: Optional[float] = Field(
        None, description="Average YOLO detection confidence score (0–1)."
    )

    class Config:
        from_attributes = True
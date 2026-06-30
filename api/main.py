"""
api/main.py
FastAPI application exposing four analytical endpoints over the dbt
star schema (public_marts schema in PostgreSQL).

"""

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import check_connection, get_db
from api.schemas import (
    ChannelActivityPoint,
    ChannelActivityResponse,
    HealthResponse,
    MessageSearchResult,
    TopProduct,
    VisualContentStat,
)

load_dotenv()

app = FastAPI(
    title="Medical Telegram Warehouse API",
    description=(
        "Analytical REST API exposing insights from Ethiopian medical and "
        "pharmaceutical Telegram channels. Data is scraped via Telethon, "
        "modelled in dbt (star schema), and enriched with YOLOv8 object detection."
    ),
    version="1.0.0",
)

# dbt materialises marts into the public_marts schema (public + _marts suffix
# from dbt_project.yml: schema: public / +schema: marts).
MARTS = "public_marts"

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="API and database health check",
)
def health():
    """Returns the API status and whether the database is reachable."""
    return HealthResponse(
        status="ok",
        database="connected" if check_connection() else "unreachable",
    )


# ---------------------------------------------------------------------------
# Endpoint 1 — Top Products
# GET /api/reports/top-products
# ---------------------------------------------------------------------------

@app.get(
    "/api/reports/top-products",
    response_model=list[TopProduct],
    tags=["Reports"],
    summary="Most frequently mentioned terms across all channels",
    description=(
        "Tokenises all message text, removes common English stop words, "
        "and returns the top N most-mentioned terms. Useful for identifying "
        "trending products or keywords across channels."
    ),
)
def top_products(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of top terms to return (1–100).",
    ),
    db: Session = Depends(get_db),
):
    sql = text(f"""
        with words as (
            select lower(regexp_split_to_table(message_text, '\\s+')) as term
            from {MARTS}.fct_messages
            where message_text is not null
        ),
        filtered as (
            select term
            from words
            where length(term) > 3
              and term not in (
                'this','that','with','from','have','been','will','they',
                'what','your','which','when','were','there','their','also',
                'more','into','than','then','some','about','would','other',
                'after','over','just','like','could','most','only','such',
                'even','those','before','very','time','year','each','well',
                'much','said','here','make','know','take','come','these'
              )
        )
        select term, count(*) as mention_count
        from filtered
        group by term
        order by mention_count desc
        limit :limit
    """)
    try:
        rows = db.execute(sql, {"limit": limit}).fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching top products: {e}",
        ) from e

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No message data found. Ensure the pipeline has been run.",
        )

    return [TopProduct(term=row.term, mention_count=row.mention_count) for row in rows]


# ---------------------------------------------------------------------------
# Endpoint 2 — Channel Activity
# GET /api/channels/{channel_name}/activity
# ---------------------------------------------------------------------------

@app.get(
    "/api/channels/{channel_name}/activity",
    response_model=ChannelActivityResponse,
    tags=["Channels"],
    summary="Posting activity and view trends for a specific channel",
    description=(
        "Returns daily post counts and average view counts for the requested "
        "channel, along with overall channel-level stats. "
        "Returns HTTP 404 if the channel name is not found in the warehouse."
    ),
)
def channel_activity(channel_name: str, db: Session = Depends(get_db)):
    # --- validate channel exists first; return 404 if not ---
    channel_sql = text(f"""
        select channel_name, total_posts, avg_views
        from {MARTS}.dim_channels
        where lower(channel_name) = lower(:channel_name)
    """)
    try:
        channel_row = db.execute(
            channel_sql, {"channel_name": channel_name}
        ).fetchone()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while looking up channel: {e}",
        ) from e

    if not channel_row:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Channel '{channel_name}' not found. "
                f"Available channels: CheMed123, lobelia4cosmetics, tikvahpharma"
            ),
        )

    # --- fetch daily activity breakdown ---
    activity_sql = text(f"""
        select
            to_char(dd.full_date, 'YYYY-MM-DD') as date,
            count(*)                              as post_count,
            round(avg(fm.view_count), 2)          as avg_views
        from {MARTS}.fct_messages fm
        join {MARTS}.dim_channels dc on fm.channel_key = dc.channel_key
        join {MARTS}.dim_dates    dd on fm.date_key    = dd.date_key
        where lower(dc.channel_name) = lower(:channel_name)
        group by dd.full_date
        order by dd.full_date
    """)
    try:
        activity_rows = db.execute(
            activity_sql, {"channel_name": channel_name}
        ).fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching channel activity: {e}",
        ) from e

    return ChannelActivityResponse(
        channel_name=channel_row.channel_name,
        total_posts=channel_row.total_posts,
        avg_views=float(channel_row.avg_views or 0),
        activity=[
            ChannelActivityPoint(
                date=row.date,
                post_count=row.post_count,
                avg_views=float(row.avg_views or 0),
            )
            for row in activity_rows
        ],
    )


# ---------------------------------------------------------------------------
# Endpoint 3 — Message Search
# GET /api/search/messages
# ---------------------------------------------------------------------------

@app.get(
    "/api/search/messages",
    response_model=list[MessageSearchResult],
    tags=["Search"],
    summary="Search messages by keyword",
    description=(
        "Case-insensitive full-text search over all scraped message content "
        "using PostgreSQL ILIKE. Results are ordered by view count descending. "
        "Returns HTTP 400 for an empty query, HTTP 404 if no results are found."
    ),
)
def search_messages(
    query: str = Query(
        ...,
        min_length=1,
        description="Keyword or phrase to search for in message text.",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of results to return (1–200).",
    ),
    db: Session = Depends(get_db),
):
    if not query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query parameter must not be blank.",
        )

    sql = text(f"""
        select
            fm.message_id,
            dc.channel_name,
            to_char(dd.full_date, 'YYYY-MM-DD') as date,
            fm.message_text,
            fm.view_count,
            fm.forward_count,
            fm.has_image
        from {MARTS}.fct_messages fm
        join {MARTS}.dim_channels dc on fm.channel_key = dc.channel_key
        join {MARTS}.dim_dates    dd on fm.date_key    = dd.date_key
        where fm.message_text ilike :query
        order by fm.view_count desc
        limit :limit
    """)
    try:
        rows = db.execute(sql, {"query": f"%{query}%", "limit": limit}).fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error during message search: {e}",
        ) from e

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No messages found containing '{query}'.",
        )

    return [
        MessageSearchResult(
            message_id=row.message_id,
            channel_name=row.channel_name,
            date=row.date,
            message_text=row.message_text,
            view_count=row.view_count,
            forward_count=row.forward_count,
            has_image=row.has_image,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Endpoint 4 — Visual Content Stats
# GET /api/reports/visual-content
# ---------------------------------------------------------------------------

@app.get(
    "/api/reports/visual-content",
    response_model=list[VisualContentStat],
    tags=["Reports"],
    summary="Image usage statistics aggregated by channel and category",
    description=(
        "Aggregates YOLO detection results from fct_image_detections by "
        "channel and image_category. Returns counts and average confidence "
        "scores for each combination of channel × category "
        "(promotional, product_display, lifestyle, other)."
    ),
)
def visual_content_stats(db: Session = Depends(get_db)):
    sql = text(f"""
        select
            dc.channel_name,
            fid.image_category,
            count(*)                                         as count,
            round(avg(fid.confidence_score)::numeric, 4)    as avg_confidence
        from {MARTS}.fct_image_detections fid
        join {MARTS}.dim_channels dc on fid.channel_key = dc.channel_key
        group by dc.channel_name, fid.image_category
        order by dc.channel_name, count desc
    """)
    try:
        rows = db.execute(sql).fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching visual content stats: {e}",
        ) from e

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No image detection data found. Ensure Task 3 pipeline has been run.",
        )

    return [
        VisualContentStat(
            channel_name=row.channel_name,
            image_category=row.image_category,
            count=row.count,
            avg_confidence=float(row.avg_confidence) if row.avg_confidence else None,
        )
        for row in rows
    ]
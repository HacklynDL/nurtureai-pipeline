"""
NurtureAI — Webhook API
FastAPI endpoint — POST /leads triggers full pipeline.
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from pipeline import process_lead

log = logging.getLogger("nurtureai.api")
app = FastAPI(title="NurtureAI API", version="1.2.0")

API_SECRET = os.getenv("WEBHOOK_SECRET", "change-me-in-production")


class LeadPayload(BaseModel):
    full_name:    str
    email:        EmailStr
    company:      str
    role:         str
    sector:       Optional[str] = ""
    source:       Optional[str] = "webhook"


class LeadResponse(BaseModel):
    status:  str
    message: str
    lead_id: Optional[str] = None


def run_pipeline(lead_data: dict):
    try:
        result = process_lead(lead_data)
        log.info(f"Pipeline complete: {result}")
    except Exception as e:
        log.error(f"Pipeline error: {e}")


@app.post("/leads", response_model=LeadResponse)
async def receive_lead(
    payload: LeadPayload,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    """
    Receive a lead and trigger the NurtureAI pipeline.
    Returns 202 immediately — pipeline runs in background.
    """
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API key")

    background_tasks.add_task(run_pipeline, payload.dict())
    return LeadResponse(
        status="accepted",
        message=f"Lead {payload.full_name} queued for processing"
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.2.0"}


@app.get("/stats")
async def stats(x_api_key: str = Header(None)):
    if x_api_key != API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API key")
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT COUNT(*) AS total,
               COUNT(CASE WHEN s.tier='A' THEN 1 END) AS tier_a,
               COUNT(CASE WHEN s.tier='B' THEN 1 END) AS tier_b,
               ROUND(AVG(s.score),1) AS avg_score
        FROM leads l LEFT JOIN scores s ON l.lead_id = s.lead_id
    """)
    result = dict(cur.fetchone())
    cur.close(); conn.close()
    return result

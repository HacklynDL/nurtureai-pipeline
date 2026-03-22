"""
NurtureAI — Main Pipeline
Webhook → Validate → Enrich → Score → Export
"""

import os
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import anthropic
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nurtureai")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
HUNTER_API_KEY    = os.getenv("HUNTER_API_KEY")
PERPLEXITY_KEY    = os.getenv("PERPLEXITY_API_KEY")
DATABASE_URL      = os.getenv("DATABASE_URL")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class Lead:
    full_name:    str
    email:        str
    company:      str
    role:         str
    sector:       str = ""
    source:       str = "webhook"
    raw_data:     dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    email:        str
    deliverable:  bool
    hunter_score: int   = 0
    is_catch_all: bool  = False
    status:       str   = "unknown"


@dataclass
class ScoringResult:
    score:                int
    tier:                 str
    fit_score:            int
    intent_score:         int
    timing_score:         int
    rationale:            str
    personalization_hook: str


def validate_email(email: str) -> ValidationResult:
    """Validate email via Hunter.io. Threshold: score >= 70."""
    try:
        r = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": HUNTER_API_KEY},
            timeout=10
        )
        data = r.json().get("data", {})
        score = data.get("score", 0)
        time.sleep(0.3)
        return ValidationResult(
            email=email,
            deliverable=(score >= 70),
            hunter_score=score,
            status=data.get("status", "unknown")
        )
    except Exception as e:
        log.warning(f"Validation error: {e}")
        return ValidationResult(email=email, deliverable=False)


ENRICH_PROMPT = """Search for the company "{company}" and provide:
1. Company overview (2-3 sentences)
2. Recent news (last 6 months)
3. Known tech stack
4. Key challenges
Facts only. Be concise."""

def enrich_company(company: str) -> dict:
    """Enrich company data via Perplexity API."""
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_KEY}"},
            json={
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{"role": "user", "content": ENRICH_PROMPT.format(company=company)}],
                "max_tokens": 600
            },
            timeout=15
        )
        return {"raw": r.json()["choices"][0]["message"]["content"]}
    except Exception as e:
        log.warning(f"Enrichment error: {e}")
        return {"raw": ""}


SCORING_PROMPT = """You are a B2B lead scoring specialist.

LEAD:
Name: {full_name} | Role: {role} | Company: {company} | Sector: {sector}
Enrichment: {enrichment}

Score this lead. Return ONLY valid JSON:
{{
  "score": <0-100>,
  "tier": "<A|B|C>",
  "fit_score": <0-100>,
  "intent_score": <0-100>,
  "timing_score": <0-100>,
  "rationale": "<2 sentences>",
  "personalization_hook": "<1 specific detail for outreach>"
}}

Tier: A=80+, B=50-79, C=below 50"""

def score_lead(lead: Lead, enrichment: dict) -> ScoringResult:
    """Score a lead using Claude."""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": SCORING_PROMPT.format(
                full_name=lead.full_name, role=lead.role,
                company=lead.company, sector=lead.sector,
                enrichment=enrichment.get("raw", "")[:600]
            )}]
        )
        data = json.loads(msg.content[0].text)
        return ScoringResult(**data)
    except Exception as e:
        log.error(f"Scoring error: {e}")
        return ScoringResult(0, "C", 0, 0, 0, "Scoring failed", "")


def save_to_db(lead, validation, enrichment, scoring) -> Optional[str]:
    """Persist pipeline results to PostgreSQL."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            INSERT INTO leads (full_name, email, company, role, sector, source, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING lead_id
        """, (lead.full_name, lead.email, lead.company, lead.role,
              lead.sector, lead.source, json.dumps(lead.raw_data)))
        lead_id = cur.fetchone()["lead_id"]
        cur.execute("""
            INSERT INTO scores (lead_id, score, tier, fit_score, intent_score,
            timing_score, rationale, personalization_hook, model_used)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (lead_id, scoring.score, scoring.tier, scoring.fit_score,
              scoring.intent_score, scoring.timing_score, scoring.rationale,
              scoring.personalization_hook, "claude-sonnet-4-20250514"))
        conn.commit()
        cur.close(); conn.close()
        return str(lead_id)
    except Exception as e:
        log.error(f"DB error: {e}")
        return None


def process_lead(lead_data: dict) -> dict:
    """Full pipeline for a single lead."""
    lead = Lead(
        full_name=lead_data.get("full_name", ""),
        email=lead_data.get("email", ""),
        company=lead_data.get("company", ""),
        role=lead_data.get("role", ""),
        sector=lead_data.get("sector", ""),
        source=lead_data.get("source", "webhook"),
        raw_data=lead_data
    )
    log.info(f"Processing: {lead.full_name} @ {lead.company}")

    validation = validate_email(lead.email)
    if not validation.deliverable:
        return {"status": "rejected", "reason": "email_invalid"}

    enrichment = enrich_company(lead.company)
    scoring = score_lead(lead, enrichment)
    lead_id = save_to_db(lead, validation, enrichment, scoring)

    log.info(f"Done — Score: {scoring.score}/100 [{scoring.tier}]")
    return {"status": "processed", "lead_id": lead_id,
            "score": scoring.score, "tier": scoring.tier}


if __name__ == "__main__":
    result = process_lead({
        "full_name": "Marie Dupont",
        "email": "m.dupont@example.com",
        "company": "TechCorp Solutions",
        "role": "Directrice Marketing",
        "sector": "SaaS B2B"
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))

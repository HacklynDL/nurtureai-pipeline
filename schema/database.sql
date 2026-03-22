-- NurtureAI Pipeline — PostgreSQL Schema v1.2.0

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE leads (
    id              SERIAL PRIMARY KEY,
    lead_id         UUID DEFAULT gen_random_uuid() UNIQUE,
    full_name       VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    email           VARCHAR(255),
    phone           VARCHAR(50),
    linkedin_url    TEXT,
    company         VARCHAR(255),
    role            VARCHAR(255),
    seniority       VARCHAR(50),
    sector          VARCHAR(100),
    company_size    VARCHAR(50),
    location        VARCHAR(100),
    source          VARCHAR(100),
    raw_data        JSONB,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE enrichments (
    id              SERIAL PRIMARY KEY,
    lead_id         UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    provider        VARCHAR(50),
    company_desc    TEXT,
    recent_news     JSONB,
    tech_stack      JSONB,
    funding_info    JSONB,
    employee_count  INTEGER,
    revenue_range   VARCHAR(50),
    raw_response    JSONB,
    enriched_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE scores (
    id                   SERIAL PRIMARY KEY,
    lead_id              UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    score                INTEGER CHECK (score BETWEEN 0 AND 100),
    tier                 CHAR(1) CHECK (tier IN ('A','B','C')),
    fit_score            INTEGER,
    intent_score         INTEGER,
    timing_score         INTEGER,
    rationale            TEXT,
    personalization_hook TEXT,
    model_used           VARCHAR(100),
    scored_at            TIMESTAMP DEFAULT NOW()
);

CREATE TABLE validations (
    id              SERIAL PRIMARY KEY,
    lead_id         UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    email_status    VARCHAR(50),
    hunter_score    INTEGER,
    mbv_score       NUMERIC(4,2),
    is_catch_all    BOOLEAN DEFAULT FALSE,
    mx_found        BOOLEAN DEFAULT FALSE,
    deliverable     BOOLEAN DEFAULT FALSE,
    validated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE campaigns (
    id            SERIAL PRIMARY KEY,
    campaign_id   UUID DEFAULT gen_random_uuid() UNIQUE,
    name          VARCHAR(255) NOT NULL,
    segment       VARCHAR(100),
    status        VARCHAR(50) DEFAULT 'draft',
    touch_count   INTEGER DEFAULT 3,
    interval_days INTEGER DEFAULT 7,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE campaign_leads (
    id           SERIAL PRIMARY KEY,
    campaign_id  UUID REFERENCES campaigns(campaign_id),
    lead_id      UUID REFERENCES leads(lead_id),
    touch_number INTEGER DEFAULT 1,
    status       VARCHAR(50) DEFAULT 'pending',
    sent_at      TIMESTAMP,
    replied_at   TIMESTAMP,
    bounce_reason TEXT,
    UNIQUE(campaign_id, lead_id)
);

CREATE INDEX idx_leads_email  ON leads(email);
CREATE INDEX idx_leads_sector ON leads(sector);
CREATE INDEX idx_scores_tier  ON scores(tier);
CREATE INDEX idx_scores_score ON scores(score DESC);
CREATE INDEX idx_cl_campaign  ON campaign_leads(campaign_id);

CREATE VIEW v_leads_scored AS
SELECT
    l.lead_id, l.full_name, l.email, l.company, l.role, l.sector,
    s.score, s.tier, s.personalization_hook, v.deliverable, l.created_at
FROM leads l
LEFT JOIN scores s ON l.lead_id = s.lead_id
LEFT JOIN validations v ON l.lead_id = v.lead_id
ORDER BY s.score DESC NULLS LAST;

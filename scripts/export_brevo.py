"""
NurtureAI — Brevo CRM Export
Format: EMAIL;PRENOM;NOM (UTF-8, semicolon delimiter)
"""

import re
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")


def format_phone(phone) -> str:
    """Convert any phone to 33XXXXXXXXX format."""
    if not phone or pd.isna(phone):
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("0") and len(digits) == 10:
        return "33" + digits[1:]
    return digits if digits.startswith("33") else ""


def fetch_leads(tier_filter: list = ["A", "B"]) -> pd.DataFrame:
    """Fetch scored, validated leads from PostgreSQL."""
    placeholders = ",".join(["%s"] * len(tier_filter))
    query = f"""
        SELECT l.lead_id, l.first_name, l.last_name, l.email,
               l.phone, l.company, l.sector,
               s.score, s.tier, s.personalization_hook
        FROM leads l
        JOIN scores s ON l.lead_id = s.lead_id
        JOIN validations v ON l.lead_id = v.lead_id
        WHERE s.tier IN ({placeholders}) AND v.deliverable = TRUE
        ORDER BY s.score DESC
    """
    conn = psycopg2.connect(DATABASE_URL)
    df = pd.read_sql_query(query, conn, params=tier_filter)
    conn.close()
    return df


def export_for_brevo(df: pd.DataFrame, output_path: str = None) -> pd.DataFrame:
    """Export to Brevo-compatible CSV."""
    brevo = pd.DataFrame()
    brevo["EMAIL"] = df["email"].str.strip().str.lower()
    brevo["PRENOM"] = df["first_name"].fillna("").str.strip()
    brevo["NOM"] = df["last_name"].fillna("").str.strip().str.upper()

    if "phone" in df.columns:
        phones = df["phone"].apply(format_phone)
        if phones.str.len().gt(0).any():
            brevo["SMS"] = phones
            brevo["LANDLINE_NUMBER"] = phones
            brevo["WHATSAPP"] = phones

    brevo = brevo[brevo["EMAIL"].str.contains("@", na=False)]
    brevo = brevo.drop_duplicates(subset=["EMAIL"])

    if not output_path:
        output_path = f"brevo_export_{datetime.now().strftime('%Y%m%d')}.csv"

    brevo.to_csv(output_path, index=False, sep=";", encoding="utf-8")
    print(f"✅ {len(brevo)} contacts exportés → {output_path}")
    return brevo


if __name__ == "__main__":
    df = fetch_leads(tier_filter=["A", "B"])
    export_for_brevo(df)

"""
database.py — SQLite storage for Jicho la Wananchi
All bills, gazette notices, executive actions, and AI summaries live here.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("jicho.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS bills (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            status      TEXT NOT NULL,
            sponsor     TEXT,
            date_tabled TEXT,
            date_passed TEXT,
            source_url  TEXT,
            raw_text    TEXT,
            summary_en  TEXT,
            summary_sw  TEXT,
            who_affected TEXT,
            key_facts   TEXT,
            vote_ayes   INTEGER DEFAULT 0,
            vote_nays   INTEGER DEFAULT 0,
            vote_absent INTEGER DEFAULT 0,
            sector      TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gazette_notices (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            notice_type TEXT,
            date_published TEXT,
            source_url  TEXT,
            raw_text    TEXT,
            summary_en  TEXT,
            summary_sw  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS executive_actions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            action_type TEXT,
            date_issued TEXT,
            source_url  TEXT,
            raw_text    TEXT,
            summary_en  TEXT,
            summary_sw  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mp_records (
            mp_id           TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            constituency    TEXT,
            party           TEXT,
            role            TEXT,
            attendance_pct  REAL DEFAULT 0,
            bills_sponsored INTEGER DEFAULT 0,
            motions_moved   INTEGER DEFAULT 0,
            questions_asked INTEGER DEFAULT 0,
            votes_participated INTEGER DEFAULT 0,
            votes_total     INTEGER DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scrape_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            status      TEXT,
            items_found INTEGER DEFAULT 0,
            items_new   INTEGER DEFAULT 0,
            error       TEXT,
            ran_at      TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
    print("✓ Database initialised")


# ── Bills ──────────────────────────────────────────────────────────────────────

def upsert_bill(bill: dict):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO bills (id, title, status, sponsor, date_tabled, source_url,
                           raw_text, sector, updated_at)
        VALUES (:id,:title,:status,:sponsor,:date_tabled,:source_url,
                :raw_text,:sector, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            status      = excluded.status,
            raw_text    = excluded.raw_text,
            updated_at  = datetime('now')
        WHERE bills.raw_text IS NULL OR bills.raw_text != excluded.raw_text
    """, bill)
    conn.commit()
    conn.close()


def update_bill_summary(bill_id: str, summary_en: str, summary_sw: str,
                        who_affected: str, key_facts: str):
    conn = get_conn()
    conn.execute("""
        UPDATE bills SET summary_en=?, summary_sw=?, who_affected=?,
                         key_facts=?, updated_at=datetime('now')
        WHERE id=?
    """, (summary_en, summary_sw, who_affected, key_facts, bill_id))
    conn.commit()
    conn.close()


def get_bills(status_filter=None, limit=50):
    conn = get_conn()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM bills WHERE status=? ORDER BY updated_at DESC LIMIT ?",
            (status_filter, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM bills ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bill(bill_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def count_bills():
    conn = get_conn()
    rows = conn.execute("""
        SELECT status, COUNT(*) as n FROM bills GROUP BY status
    """).fetchall()
    conn.close()
    return {r["status"]: r["n"] for r in rows}


# ── Gazette ────────────────────────────────────────────────────────────────────

def upsert_gazette(notice: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO gazette_notices
            (id, title, notice_type, date_published, source_url, raw_text)
        VALUES (:id,:title,:notice_type,:date_published,:source_url,:raw_text)
    """, notice)
    conn.commit()
    conn.close()


def update_gazette_summary(notice_id: str, summary_en: str, summary_sw: str):
    conn = get_conn()
    conn.execute(
        "UPDATE gazette_notices SET summary_en=?, summary_sw=? WHERE id=?",
        (summary_en, summary_sw, notice_id)
    )
    conn.commit()
    conn.close()


def get_gazette_notices(limit=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM gazette_notices ORDER BY date_published DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Executive actions ──────────────────────────────────────────────────────────

def upsert_executive_action(action: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO executive_actions
            (id, title, action_type, date_issued, source_url, raw_text)
        VALUES (:id,:title,:action_type,:date_issued,:source_url,:raw_text)
    """, action)
    conn.commit()
    conn.close()


def update_executive_summary(action_id: str, summary_en: str, summary_sw: str):
    conn = get_conn()
    conn.execute(
        "UPDATE executive_actions SET summary_en=?, summary_sw=? WHERE id=?",
        (summary_en, summary_sw, action_id)
    )
    conn.commit()
    conn.close()


def get_executive_actions(limit=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM executive_actions ORDER BY date_issued DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── MPs ────────────────────────────────────────────────────────────────────────

def upsert_mp(mp: dict):
    conn = get_conn()
    conn.execute("""
        INSERT INTO mp_records (mp_id, name, constituency, party, role)
        VALUES (:mp_id,:name,:constituency,:party,:role)
        ON CONFLICT(mp_id) DO UPDATE SET
            attendance_pct     = excluded.attendance_pct,
            bills_sponsored    = excluded.bills_sponsored,
            motions_moved      = excluded.motions_moved,
            questions_asked    = excluded.questions_asked,
            votes_participated = excluded.votes_participated,
            votes_total        = excluded.votes_total,
            updated_at         = datetime('now')
    """, mp)
    conn.commit()
    conn.close()


def get_mps(limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM mp_records ORDER BY name ASC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Scrape log ─────────────────────────────────────────────────────────────────

def log_scrape(source: str, status: str, items_found=0, items_new=0, error=None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO scrape_log (source, status, items_found, items_new, error)
        VALUES (?,?,?,?,?)
    """, (source, status, items_found, items_new, error))
    conn.commit()
    conn.close()


def get_last_scrape_times():
    conn = get_conn()
    rows = conn.execute("""
        SELECT source, MAX(ran_at) as last_run, status
        FROM scrape_log GROUP BY source
    """).fetchall()
    conn.close()
    return {r["source"]: {"last_run": r["last_run"], "status": r["status"]} for r in rows}

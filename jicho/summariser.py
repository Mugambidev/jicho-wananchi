"""
summariser.py — Claude-powered plain-language summarisation engine
Takes raw bill text / gazette notices and returns structured summaries
in both English and Kiswahili.
"""
import os
import json
import anthropic
from database import (
    get_bills, update_bill_summary,
    get_gazette_notices, update_gazette_summary,
    get_executive_actions, update_executive_summary,
    log_scrape
)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

BILL_SYSTEM = """You are the AI engine for Jicho la Wananchi (The People's Eye), 
a non-partisan civic education platform for Kenya. Your job is to read raw 
legislative text and extract factual information in plain language that any 
Kenyan citizen can understand — whether they are a farmer in Kisumu, a student 
in Mombasa, or a trader in Nairobi.

Rules:
- Be factual and neutral. Never editorialize. Never say a bill is "good" or "bad".
- Use simple, clear language. Avoid legal jargon.
- Be specific: mention actual numbers, percentages, and dates where present.
- If something is unclear or missing from the text, say so — never invent facts.
- Keep summaries concise but complete.

Return ONLY valid JSON. No markdown, no preamble."""

BILL_PROMPT = """Analyse this Kenya National Assembly bill and return a JSON object with exactly these fields:

{
  "summary_en": "2-3 sentence plain English summary of what this bill does and why it matters to ordinary Kenyans. Mention specific figures if present.",
  "summary_sw": "2-3 sentence plain Kiswahili translation/summary of the same. Use everyday Kiswahili, not bureaucratic language.",
  "who_affected": "Comma-separated list of groups directly affected, e.g. 'PAYE workers, informal sector traders, small business owners'",
  "key_facts": "JSON array of 3-5 specific factual bullet points, each under 20 words. Format: [{\"fact\": \"...\"}]"
}

Bill text:
---
{text}
---"""

GAZETTE_SYSTEM = """You are the AI engine for Jicho la Wananchi, a Kenyan civic 
education platform. Summarise Kenya Gazette notices in plain language for citizens.
Return ONLY valid JSON."""

GAZETTE_PROMPT = """Summarise this Kenya Gazette notice:

{
  "summary_en": "2-3 sentence plain English summary of what this notice means for Kenyans.",
  "summary_sw": "Same summary in plain Kiswahili."
}

Notice text:
---
{text}
---"""


def summarise_bill(bill: dict) -> dict | None:
    """Run a bill through Claude and return structured summary fields."""
    raw = bill.get("raw_text", "")
    if not raw or len(raw.strip()) < 100:
        return None

    # Truncate very long bills to ~12,000 chars (still very long)
    text = raw[:12000] + ("..." if len(raw) > 12000 else "")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=BILL_SYSTEM,
            messages=[{
                "role": "user",
                "content": BILL_PROMPT.format(text=text)
            }]
        )
        raw_json = response.content[0].text.strip()
        # Strip accidental markdown fences
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
        data = json.loads(raw_json)
        # Flatten key_facts if it's a list of dicts
        if isinstance(data.get("key_facts"), list):
            data["key_facts"] = json.dumps(data["key_facts"])
        return data
    except Exception as e:
        print(f"  ✗ Summarise bill {bill['id']}: {e}")
        return None


def summarise_gazette(notice: dict) -> dict | None:
    raw = notice.get("raw_text", "")
    if not raw or len(raw.strip()) < 50:
        return None
    text = raw[:6000]
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=GAZETTE_SYSTEM,
            messages=[{
                "role": "user",
                "content": GAZETTE_PROMPT.format(text=text)
            }]
        )
        raw_json = response.content[0].text.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
        return json.loads(raw_json)
    except Exception as e:
        print(f"  ✗ Summarise gazette {notice['id']}: {e}")
        return None


def run_summarisation():
    """
    Main summarisation job — runs after each scrape.
    Finds all items without summaries and processes them.
    """
    print("\n── AI Summarisation Engine ──────────────────────────")

    # Bills without summaries
    bills = get_bills(limit=200)
    unsummarised_bills = [b for b in bills if not b.get("summary_en")]
    print(f"  Bills needing summaries: {len(unsummarised_bills)}")

    bill_count = 0
    for bill in unsummarised_bills:
        print(f"  → Summarising: {bill['title'][:60]}...")
        result = summarise_bill(bill)
        if result:
            update_bill_summary(
                bill["id"],
                result.get("summary_en", ""),
                result.get("summary_sw", ""),
                result.get("who_affected", ""),
                result.get("key_facts", "[]")
            )
            bill_count += 1

    # Gazette notices without summaries
    notices = get_gazette_notices(limit=100)
    unsummarised = [n for n in notices if not n.get("summary_en")]
    print(f"  Gazette notices needing summaries: {len(unsummarised)}")

    gazette_count = 0
    for notice in unsummarised:
        print(f"  → Summarising gazette: {notice['title'][:60]}...")
        result = summarise_gazette(notice)
        if result:
            update_gazette_summary(
                notice["id"],
                result.get("summary_en", ""),
                result.get("summary_sw", "")
            )
            gazette_count += 1

    # Executive actions without summaries
    actions = get_executive_actions(limit=100)
    unsummarised_actions = [a for a in actions if not a.get("summary_en")]
    print(f"  Executive actions needing summaries: {len(unsummarised_actions)}")

    action_count = 0
    for action in unsummarised_actions:
        print(f"  → Summarising action: {action['title'][:60]}...")
        result = summarise_gazette(action)  # reuse gazette prompt — same format
        if result:
            update_executive_summary(
                action["id"],
                result.get("summary_en", ""),
                result.get("summary_sw", "")
            )
            action_count += 1

    log_scrape("summariser", "success",
               items_found=len(unsummarised_bills) + len(unsummarised) + len(unsummarised_actions),
               items_new=bill_count + gazette_count + action_count)

    print(f"  ✓ Summarised: {bill_count} bills, {gazette_count} notices, {action_count} actions")
    print("─────────────────────────────────────────────────────\n")

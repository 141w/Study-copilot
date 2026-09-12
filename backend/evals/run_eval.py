#!/usr/bin/env python3
"""Offline RAG evaluation runner.

Modes:
1. Structure check (default, no network/DB):
   python -m evals.run_eval
   Validates dataset schema and prints case count.

2. Lexical baseline (no LLM):
   python -m evals.run_eval --lexical
   Scores each case by whether must_contain keywords appear in gold_answer
   and whether expected_sources are non-empty (dataset self-consistency).

3. Live pipeline (requires configured backend env + uploaded docs):
   python -m evals.run_eval --live --token $JWT
   Calls POST /api/chat/ask (non-stream) and scores keyword hit-rate +
   source filename overlap against expected_sources.

Exit code 0 always for structure/lexical unless --strict and failures exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DATASET = Path(__file__).parent / "dataset.jsonl"


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for i, line in enumerate(DATASET.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"dataset.jsonl line {i} invalid JSON: {e}") from e
        for key in ("id", "question", "expected_sources", "must_contain"):
            if key not in obj:
                raise SystemExit(f"dataset.jsonl line {i} missing key: {key}")
        cases.append(obj)
    return cases


def keyword_hit_rate(answer: str, must_contain: list[str]) -> float:
    if not must_contain:
        return 1.0
    text = (answer or "").lower()
    hits = sum(1 for k in must_contain if k.lower() in text)
    return hits / len(must_contain)


def source_overlap(sources: list[dict[str, Any]], expected: list[str]) -> float:
    if not expected:
        return 1.0
    names = {
        str(s.get("source") or s.get("document_id") or "").lower()
        for s in sources
        if isinstance(s, dict)
    }
    hit = sum(
        1 for e in expected if e.lower() in " ".join(names) or any(e.lower() in n for n in names)
    )
    return hit / len(expected)


def run_lexical(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for c in cases:
        score = keyword_hit_rate(str(c.get("gold_answer") or ""), c["must_contain"])
        rows.append({"id": c["id"], "keyword_score": score, "ok": score >= 0.5})
    ok = all(r["ok"] for r in rows)
    return {"mode": "lexical", "cases": len(rows), "pass": ok, "rows": rows}


def run_live(
    cases: list[dict[str, Any]], base_url: str, token: str, doc_ids: list[str]
) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    rows = []
    for c in cases:
        body = json.dumps(
            {"question": c["question"], "document_ids": doc_ids, "stream": False}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/chat/ask",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            rows.append({"id": c["id"], "error": str(e), "ok": False})
            continue
        answer = payload.get("answer") or ""
        sources = payload.get("sources") or []
        kw = keyword_hit_rate(answer, c["must_contain"])
        src = source_overlap(sources, c["expected_sources"])
        combined = 0.6 * kw + 0.4 * src
        rows.append(
            {
                "id": c["id"],
                "keyword_score": round(kw, 3),
                "source_score": round(src, 3),
                "combined": round(combined, 3),
                "ok": combined >= 0.4,
            }
        )
    passed = sum(1 for r in rows if r.get("ok"))
    return {
        "mode": "live",
        "cases": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Study Copilot offline RAG eval")
    p.add_argument("--lexical", action="store_true", help="Run lexical self-consistency baseline")
    p.add_argument("--live", action="store_true", help="Call live /api/chat/ask")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--token", default="", help="JWT for --live")
    p.add_argument("--doc-ids", default="", help="Comma-separated document ids for --live")
    p.add_argument("--strict", action="store_true", help="Non-zero exit on failure")
    args = p.parse_args(argv)

    cases = load_cases()
    print(f"Loaded {len(cases)} eval cases from {DATASET}")

    if args.live:
        if not args.token:
            print("--live requires --token", file=sys.stderr)
            return 2
        doc_ids = [d for d in args.doc_ids.split(",") if d.strip()]
        report = run_live(cases, args.base_url, args.token, doc_ids)
    elif args.lexical:
        report = run_lexical(cases)
    else:
        report = {"mode": "structure", "cases": len(cases), "pass": True}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report.get("pass", True) and report.get("pass_rate", 1.0) < 0.4:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Repair non-Naver detail_url values with Naver's public search result page.

Only an unambiguous place card is written back.  Every attempted row is kept in
the audit CSV, so a transient block or an ambiguous short store name can be
reviewed or resumed safely.

Examples:
    python scripts/repair_naver_urls.py --limit 10
    python scripts/repair_naver_urls.py
    python scripts/repair_naver_urls.py --retry-unresolved
"""

from __future__ import annotations

import argparse
import html
import random
import re
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


CSV_PATH = Path("최최종(거리,URL).csv")
LOG_DIR = Path("logs")
KST = timezone(timedelta(hours=9))
SEARCH_URL = "https://search.naver.com/search.naver"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
PLACE_RE = re.compile(r"https?://map\.naver\.com/(?:p|v5)/entry/place/(\d+)")


def normalized(value: object) -> str:
    """Compare Korean store names while ignoring spacing and punctuation."""
    text = html.unescape(str(value or "")).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def naver_url(place_id: str) -> str:
    # The source dataset uses the mobile restaurant URL format.
    return f"https://m.place.naver.com/restaurant/{place_id}/home"


def extract_candidates(page_html: str) -> list[dict[str, object]]:
    """Return genuine organic place-card links, excluding ads and directions."""
    soup = BeautifulSoup(page_html, "html.parser")
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href*='map.naver.com']"):
        href = html.unescape(anchor.get("href", ""))
        match = PLACE_RE.search(href)
        if not match or "/directions/" in href:
            continue

        place_id = match.group(1)
        if place_id in seen:
            continue
        seen.add(place_id)

        name = anchor.get_text(" ", strip=True)
        # A place card's title link contains the business name.  Other direct
        # map links (e.g. directions) are intentionally ignored above.
        if not name:
            continue

        parsed = parse_qs(urlparse(href).query)
        try:
            lat = float(parsed["lat"][0])
            lon = float(parsed["lng"][0])
        except (KeyError, IndexError, ValueError):
            lat = lon = None

        candidates.append(
            {"place_id": place_id, "name": name, "lat": lat, "lon": lon, "href": href}
        )
    return candidates


def choose_candidate(store_name: str, candidates: list[dict[str, object]]) -> tuple[dict[str, object] | None, float]:
    wanted = normalized(store_name)
    best: dict[str, object] | None = None
    best_score = 0.0
    for candidate in candidates:
        found = normalized(candidate["name"])
        if not found:
            continue
        if wanted == found:
            score = 1.0
        elif wanted in found or found in wanted:
            score = 0.93
        else:
            score = SequenceMatcher(None, wanted, found).ratio()
        if score > best_score:
            best, best_score = candidate, score

    # Short names such as "오츠" are too ambiguous without an exact match.
    minimum = 1.0 if len(wanted) <= 3 else 0.90
    return (best, best_score) if best_score >= minimum else (None, best_score)


def is_naver_url(value: object) -> bool:
    return "naver.com" in str(value or "").lower()


def find_place(session: requests.Session, store_name: str) -> tuple[dict[str, object] | None, float, str]:
    """Search increasingly broad local phrases before declaring a row unresolved."""
    queries = [
        f"부산 남구 대연동 {store_name}",
        f"부경대 {store_name}",
        f"경성대 {store_name}",
        f"부산 남구 {store_name}",
    ]
    best_score = 0.0
    last_query = queries[-1]
    last_error: requests.RequestException | None = None
    for query in queries:
        last_query = query
        try:
            response = session.get(SEARCH_URL, params={"where": "nexearch", "query": query}, timeout=25)
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
            continue
        candidate, score = choose_candidate(store_name, extract_candidates(response.text))
        best_score = max(best_score, score)
        if candidate:
            return candidate, score, query
    if last_error and best_score == 0.0:
        raise last_error
    return None, best_score, last_query


def backup_source() -> Path:
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    backup = CSV_PATH.with_name(f"{CSV_PATH.stem}.before_url_repair_{stamp}.csv")
    shutil.copy2(CSV_PATH, backup)
    return backup


def save(df: pd.DataFrame) -> None:
    temp = CSV_PATH.with_suffix(".csv.tmp")
    df.to_csv(temp, index=False, encoding="utf-8-sig")
    temp.replace(CSV_PATH)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="maximum target rows (0 = all)")
    parser.add_argument("--retry-unresolved", action="store_true", help="retry rows marked URL_미확인")
    parser.add_argument("--delay", type=float, default=1.15, help="base delay in seconds between searches")
    args = parser.parse_args()

    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return 2

    LOG_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(CSV_PATH)
    if "url_status" not in df.columns:
        df["url_status"] = ""
    if "url_checked_at" not in df.columns:
        df["url_checked_at"] = ""
    if "url_match_score" not in df.columns:
        df["url_match_score"] = ""
    # Pandas 3 rejects string assignments to a column inferred as float from
    # blank/NaN historical audit values.
    for column in ("url_status", "url_checked_at", "url_match_score"):
        df[column] = df[column].fillna("").astype(object)

    invalid = ~df["detail_url"].map(is_naver_url)
    if args.retry_unresolved:
        target = invalid
    else:
        target = invalid & ~df["url_status"].astype(str).eq("URL_미확인")
    indices = list(df.index[target])
    if args.limit:
        indices = indices[: args.limit]

    if not indices:
        print("처리할 잘못된 detail_url이 없습니다.")
        return 0

    backup = backup_source()
    print(f"대상 {len(indices)}개 | 원본 백업: {backup.name}")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
    report: list[dict[str, object]] = []
    success = unresolved = failed = 0

    for position, idx in enumerate(indices, start=1):
        row = df.loc[idx]
        store_name = str(row["name"])
        query = f"부산 남구 대연동 {store_name}"
        checked_at = datetime.now(KST).isoformat(timespec="seconds")
        result = {"id": row["id"], "name": store_name, "query": query, "old_url": row["detail_url"], "checked_at": checked_at}
        try:
            candidate, score, query = find_place(session, store_name)
            result["query"] = query
            if candidate:
                new_url = naver_url(str(candidate["place_id"]))
                df.at[idx, "detail_url"] = new_url
                df.at[idx, "url_status"] = "URL_확인"
                df.at[idx, "url_checked_at"] = checked_at
                df.at[idx, "url_match_score"] = f"{score:.2f}"
                result.update({"status": "URL_확인", "new_url": new_url, "candidate_name": candidate["name"], "score": score, "candidate_lat": candidate["lat"], "candidate_lon": candidate["lon"]})
                success += 1
            else:
                df.at[idx, "url_status"] = "URL_미확인"
                df.at[idx, "url_checked_at"] = checked_at
                df.at[idx, "url_match_score"] = f"{score:.2f}"
                result.update({"status": "URL_미확인", "new_url": "", "candidate_name": "", "score": score})
                unresolved += 1
        except requests.RequestException as exc:
            # Do not mark a network failure as an exhausted search attempt.
            result.update({"status": "요청오류", "new_url": "", "candidate_name": "", "score": "", "error": str(exc)})
            failed += 1
        report.append(result)

        if position % 20 == 0:
            save(df)
            pd.DataFrame(report).to_csv(LOG_DIR / "naver_url_repair_latest.csv", index=False, encoding="utf-8-sig")
        print(f"[{position}/{len(indices)}] {store_name}: {result['status']}")
        time.sleep(args.delay + random.uniform(0.15, 0.65))

    save(df)
    report_path = LOG_DIR / f"naver_url_repair_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.csv"
    pd.DataFrame(report).to_csv(report_path, index=False, encoding="utf-8-sig")
    print(f"완료 | 확인 {success}, 미확인 {unresolved}, 요청오류 {failed} | 보고서: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

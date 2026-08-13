"""Create an auditable clean export without deleting source rows.

The original CSV remains the working ledger.  This script adds a clear status to
every row, exports the complete reviewed ledger, and exports only usable rows
for the map/application.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


SOURCE = Path("최최종(거리,URL).csv")
REVIEWED = Path("최최종_검토완료.csv")
ACTIVE = Path("최최종_활성데이터.csv")


def numeric_distance(value: object) -> bool:
    return bool(re.fullmatch(r"\d+", str(value or "").strip()))


def has_naver_url(value: object) -> bool:
    return "naver.com" in str(value or "").lower()


def classify(row: pd.Series) -> str:
    if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
        return "폐업추정_좌표없음"
    if not has_naver_url(row.get("detail_url")):
        return "검토필요_URL미확인"
    if numeric_distance(row.get("distance")):
        return "활성"
    if str(row.get("distance") or "").strip() == "경로없음":
        return "도보경로없음"
    return "검토필요_거리미측정"


def main() -> None:
    df = pd.read_csv(SOURCE)
    df["data_status"] = df.apply(classify, axis=1)
    df.to_csv(REVIEWED, index=False, encoding="utf-8-sig")

    active = df[df["data_status"].eq("활성")].copy()
    active.to_csv(ACTIVE, index=False, encoding="utf-8-sig")

    print(df["data_status"].value_counts().to_string())
    print(f"검토용 전체 파일: {REVIEWED}")
    print(f"앱 사용 가능 데이터: {ACTIVE} ({len(active)}개)")


if __name__ == "__main__":
    main()

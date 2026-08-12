# -*- coding: utf-8 -*-
"""
matcher.py - 에브리타임 음식점 매칭 엔진
==========================================
에브리타임 팀이 전달한 음식점 이름을 사전 수집된 DB와 매칭하고,
매칭된 결과를 matched_results.json으로 출력합니다.

[매칭 알고리즘]
1단계: 정확 매칭 (정규화된 이름이 완전히 일치)
2단계: 부분 매칭 (입력 이름이 DB 이름에 포함)
3단계: DB에 없으면 → 네이버 API로 실시간 검색 → 반경 확인 → DB 추가

[사용법]
  python matcher.py                                    # 기본 입력 파일 사용
  python matcher.py --input data/input_restaurants.txt  # 입력 파일 지정
"""

import sys
import io
import os
import json
import argparse
from datetime import datetime

import config
from utils import normalize_name, is_within_radius, format_distance
from collector import search_naver_local, process_api_item, save_database

# Windows 콘솔 UTF-8 호환
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ==============================================================================
# DB 로드
# ==============================================================================

def load_database():
    """
    restaurants_db.json에서 음식점 데이터를 로드합니다.

    Returns:
        list: 음식점 딕셔너리 리스트
        None: 파일이 없거나 파싱 실패 시
    """
    if not os.path.exists(config.RESTAURANTS_DB_PATH):
        print("[경고] restaurants_db.json이 없습니다.")
        print("       먼저 collector.py를 실행하여 데이터를 수집하세요.")
        return None

    try:
        with open(config.RESTAURANTS_DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        restaurants = db.get("restaurants", [])
        print(f"[DB] {len(restaurants)}개 음식점 데이터 로드 완료")
        return restaurants
    except (json.JSONDecodeError, IOError) as e:
        print(f"[오류] DB 파일 읽기 실패: {e}")
        return None


# ==============================================================================
# 입력 파일 로드
# ==============================================================================

def load_input_names(filepath):
    """
    에브리타임 팀에서 전달받은 음식점 이름 목록을 파일에서 로드합니다.

    지원 형식:
    - .txt: 줄바꿈으로 구분된 음식점 이름
    - .json: ["이름1", "이름2", ...] 배열

    Args:
        filepath (str): 입력 파일 경로

    Returns:
        list: 음식점 이름 문자열 리스트
    """
    if not os.path.exists(filepath):
        print(f"[오류] 입력 파일을 찾을 수 없습니다: {filepath}")
        return []

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            names = json.load(f)
            if isinstance(names, list):
                return [n.strip() for n in names if n.strip()]
    else:
        # .txt 또는 기타: 줄바꿈 구분
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return [line.strip() for line in lines if line.strip()]

    return []


# ==============================================================================
# 매칭 알고리즘
# ==============================================================================

def match_restaurant(name, db_restaurants):
    """
    입력된 음식점 이름을 DB에서 매칭합니다.

    [매칭 우선순위]
    1. 정확 매칭: 정규화된 이름이 완전히 일치
       예: "홍콩반점" → "홍콩반점경성대점" (X, 부분 매칭)
       예: "홍콩반점경성대점" → "홍콩반점경성대점" (O, 정확 매칭)

    2. 부분 매칭: 입력 이름이 DB 이름에 포함
       예: "홍콩반점" → "홍콩반점경성대점" (O)
       예: "스시로" → "스시로부산대연점" (O)

    Args:
        name (str): 에브리타임에서 받은 음식점 이름
        db_restaurants (list): DB의 음식점 리스트

    Returns:
        dict or None: 매칭된 음식점 정보, 없으면 None
    """
    normalized_input = normalize_name(name)

    if not normalized_input:
        return None

    # 1단계: 정확 매칭
    for rest in db_restaurants:
        if rest.get("name_normalized") == normalized_input:
            return rest

    # 2단계: 부분 매칭 (입력이 DB에 포함되거나, DB가 입력에 포함)
    candidates = []
    for rest in db_restaurants:
        db_norm = rest.get("name_normalized", "")
        if normalized_input in db_norm or db_norm in normalized_input:
            candidates.append(rest)

    if candidates:
        # 여러 후보가 있으면 거리가 가장 가까운 것 선택
        candidates.sort(key=lambda r: r.get("distance_km", 999))
        return candidates[0]

    return None


def search_and_add(name, db_restaurants):
    """
    DB에 없는 음식점을 네이버 API로 실시간 검색하고,
    반경 내에 있으면 DB에 추가합니다.

    Args:
        name (str): 음식점 이름
        db_restaurants (list): 현재 DB 리스트 (새 항목 추가용)

    Returns:
        dict or None: 검색 결과 음식점, 없으면 None
    """
    if config.DEMO_MODE:
        print(f"    [데모 모드] '{name}' API 검색 건너뜀")
        return None

    # 학교 지역 + 음식점 이름으로 검색
    query = f"{config.SEARCH_AREA_KEYWORDS[0]} {name}"
    print(f"    [API 검색] '{query}'")

    items = search_naver_local(query, display=3)
    if not items:
        return None

    # 첫 번째 결과가 반경 내인지 확인
    for item in items:
        processed = process_api_item(item, query)

        if is_within_radius(
            processed["lat"], processed["lng"],
            config.SCHOOL_LAT, config.SCHOOL_LNG,
            config.SEARCH_RADIUS_KM,
        ):
            # DB에 추가
            db_restaurants.append(processed)
            print(f"    [추가] {processed['name']} ({format_distance(processed['distance_km'])})")
            return processed

    print(f"    [미발견] 반경 {config.SEARCH_RADIUS_KM}km 내에서 찾을 수 없음")
    return None


# ==============================================================================
# 매칭 파이프라인 실행
# ==============================================================================

def run_matching(input_filepath=None):
    """
    전체 매칭 파이프라인을 실행합니다.

    [흐름]
    1. DB 로드
    2. 입력 파일에서 음식점 이름 로드
    3. 각 이름에 대해 매칭 수행
    4. 결과를 matched_results.json으로 저장
    """
    print("=" * 60)
    print("  에브리타임 음식점 매칭 엔진 v1.0")
    print("=" * 60)

    # (1) DB 로드
    db_restaurants = load_database()
    if db_restaurants is None:
        print("\n[중단] DB가 없습니다. 먼저 collector.py를 실행하세요.")
        print("       python collector.py")
        return

    # (2) 입력 파일 로드
    input_path = input_filepath or config.INPUT_FILE_PATH
    input_names = load_input_names(input_path)

    if not input_names:
        print(f"\n[중단] 입력 파일이 비어있거나 찾을 수 없습니다: {input_path}")
        return

    print(f"\n[입력] {len(input_names)}개 음식점 이름 로드:")
    for name in input_names:
        print(f"  - {name}")

    # (3) 매칭 수행
    print(f"\n{'='*60}")
    print("  매칭 시작")
    print(f"{'='*60}")

    matched = []
    unmatched = []

    for i, name in enumerate(input_names, 1):
        print(f"\n  [{i}/{len(input_names)}] '{name}'")

        # DB에서 매칭 시도
        result = match_restaurant(name, db_restaurants)

        if result:
            print(f"    [매칭 성공] -> {result['name']} ({result['category']})")
            matched.append({
                "input_name": name,
                "matched": True,
                "restaurant": result,
            })
        else:
            # DB에 없으면 API로 실시간 검색
            print(f"    [DB 미매칭] API 검색 시도...")
            api_result = search_and_add(name, db_restaurants)

            if api_result:
                matched.append({
                    "input_name": name,
                    "matched": True,
                    "restaurant": api_result,
                })
            else:
                print(f"    [최종 미매칭] '{name}'")
                unmatched.append(name)

    # (4) 결과 저장
    output = {
        "metadata": {
            "school_name": config.SCHOOL_NAME,
            "school_lat": config.SCHOOL_LAT,
            "school_lng": config.SCHOOL_LNG,
            "radius_km": config.SEARCH_RADIUS_KM,
            "generated_at": datetime.now().isoformat(),
            "total_input": len(input_names),
            "matched_count": len(matched),
            "unmatched_count": len(unmatched),
        },
        "matched_restaurants": [m["restaurant"] for m in matched],
        "unmatched_names": unmatched,
    }

    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.MATCHED_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # DB도 갱신 (API 검색으로 추가된 항목 반영)
    if not config.DEMO_MODE:
        save_database(db_restaurants)

    # (5) 결과 요약 출력
    print(f"\n{'='*60}")
    print(f"  매칭 결과 요약")
    print(f"{'='*60}")
    print(f"  입력:       {len(input_names)}개")
    print(f"  매칭 성공:  {len(matched)}개")
    print(f"  매칭 실패:  {len(unmatched)}개")
    print(f"  매칭률:     {len(matched)/len(input_names)*100:.1f}%")
    print(f"\n  결과 파일: {config.MATCHED_RESULTS_PATH}")

    if unmatched:
        print(f"\n  [미매칭 목록]")
        for name in unmatched:
            print(f"    - {name}")

    print(f"{'='*60}")

    return output


# ==============================================================================
# 메인 실행부
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="에브리타임 음식점 매칭 엔진")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="입력 파일 경로 (기본: data/input_restaurants.txt)",
    )
    args = parser.parse_args()

    run_matching(input_filepath=args.input)

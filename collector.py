# -*- coding: utf-8 -*-
"""
collector.py - 네이버 Local Search API 음식점 수집기
=====================================================
학교 주변 음식점 데이터를 네이버 검색 API로 수집하고,
반경 700m 내의 결과만 필터링하여 restaurants_db.json에 저장합니다.

[사용법]
  python collector.py          # 전체 수집 실행
  python collector.py --test   # 테스트 모드 (1개 카테고리만)

[필요한 API 키]
  - NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (.env 파일에 설정)
  - 키가 없으면 데모 모드로 Mock 데이터 생성
"""

import sys
import io
import os
import json
import time
import hashlib
import argparse
from datetime import datetime

import requests

# 프로젝트 모듈 임포트
import config
from utils import (
    katec_to_wgs84,
    haversine_distance,
    clean_html_tags,
    normalize_name,
    is_within_radius,
    format_distance,
)

# Windows 콘솔 UTF-8 호환
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ==============================================================================
# 네이버 Local Search API 호출
# ==============================================================================

def search_naver_local(query, display=5, start=1):
    """
    네이버 Local Search API를 호출하여 검색 결과를 반환합니다.

    Args:
        query (str): 검색어 (예: "경성대 한식")
        display (int): 한 번에 가져올 결과 수 (1~5)
        start (int): 검색 시작 위치 (1~)

    Returns:
        list: 검색된 업체 정보 리스트 (items)
        None: API 호출 실패 시
    """
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": config.NAVER_LOCAL_SEARCH_SORT,
    }

    try:
        response = requests.get(
            config.NAVER_LOCAL_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("items", [])

    except requests.exceptions.HTTPError as e:
        print(f"  [API 오류] HTTP {response.status_code}: {e}")
        if response.status_code == 401:
            print("  -> API 키가 유효하지 않습니다. .env 파일을 확인하세요.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [네트워크 오류] {e}")
        return None


def process_api_item(item, query):
    """
    네이버 Local Search API의 개별 응답 아이템을 정제하여
    통일된 형식의 딕셔너리로 변환합니다.

    Args:
        item (dict): API 응답의 개별 아이템
        query (str): 사용된 검색어

    Returns:
        dict: 정제된 음식점 정보
    """
    # 상호명에서 HTML 태그 제거
    name = clean_html_tags(item.get("title", ""))

    # 카텍 좌표 -> WGS84 위경도 변환
    lat, lng = katec_to_wgs84(item.get("mapx", 0), item.get("mapy", 0))

    # 학교로부터의 거리 계산
    distance = haversine_distance(
        lat, lng, config.SCHOOL_LAT, config.SCHOOL_LNG
    )

    # 고유 ID 생성 (이름 + 주소 기반 해시)
    raw_id = f"{name}_{item.get('address', '')}"
    rest_id = "rest_" + hashlib.md5(raw_id.encode("utf-8")).hexdigest()[:8]

    return {
        "id": rest_id,
        "name": name,
        "name_normalized": normalize_name(name),
        "category": item.get("category", ""),
        "address": item.get("address", ""),
        "road_address": item.get("roadAddress", ""),
        "phone": item.get("telephone", ""),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "distance_km": round(distance, 2),
        "naver_link": item.get("link", ""),
        "description": item.get("description", ""),
        "crawled_data": {
            "visitor_review_count": 0,
            "blog_review_count": 0,
            "rating": "N/A",
            "keywords": [],
        },
        "source": "naver_local_api",
        "search_query": query,
        "collected_at": datetime.now().isoformat(),
    }


# ==============================================================================
# 데모 모드용 Mock 데이터 생성
# ==============================================================================

def generate_demo_data():
    """
    API 키가 없는 경우 테스트용 Mock 데이터를 생성합니다.
    실제 경성대 주변 음식점을 모사한 데이터입니다.
    """
    print("[데모 모드] API 키가 설정되지 않아 Mock 데이터를 생성합니다.")
    print("  -> .env 파일에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET을 설정하면")
    print("     실제 API 데이터로 전환됩니다.\n")

    demo_restaurants = [
        {
            "id": "rest_demo_001",
            "name": "홍콩반점 경성대점",
            "name_normalized": "홍콩반점경성대점",
            "category": "중국식>중국요리",
            "address": "부산 남구 대연동 55-1",
            "road_address": "부산 남구 수영로 316",
            "phone": "051-621-0410",
            "lat": 35.1385,
            "lng": 129.0985,
            "distance_km": 2.8,
            "naver_link": "",
            "description": "중화요리 전문점",
            "crawled_data": {
                "visitor_review_count": 128,
                "blog_review_count": 45,
                "rating": "4.2",
                "keywords": ["짬뽕 맛집", "가성비"],
            },
            "source": "demo",
            "search_query": "경성대 중식",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_002",
            "name": "스시로 부산대연점",
            "name_normalized": "스시로부산대연점",
            "category": "일식>초밥,롤",
            "address": "부산 남구 대연동 120-3",
            "road_address": "부산 남구 용소로 15",
            "phone": "051-555-1234",
            "lat": 35.1400,
            "lng": 129.0750,
            "distance_km": 1.2,
            "naver_link": "",
            "description": "회전 초밥 전문점",
            "crawled_data": {
                "visitor_review_count": 256,
                "blog_review_count": 89,
                "rating": "4.5",
                "keywords": ["초밥 맛집", "가족모임"],
            },
            "source": "demo",
            "search_query": "경성대 일식",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_003",
            "name": "맘스터치 경성대점",
            "name_normalized": "맘스터치경성대점",
            "category": "패스트푸드>햄버거",
            "address": "부산 남구 대연3동 49-16",
            "road_address": "부산 남구 수영로328번길 3",
            "phone": "051-622-8282",
            "lat": 35.1415,
            "lng": 129.0680,
            "distance_km": 0.3,
            "naver_link": "",
            "description": "싸이버거 맛집",
            "crawled_data": {
                "visitor_review_count": 312,
                "blog_review_count": 67,
                "rating": "4.0",
                "keywords": ["싸이버거", "가성비 햄버거"],
            },
            "source": "demo",
            "search_query": "경성대 햄버거",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_004",
            "name": "역전할머니맥주 경성대점",
            "name_normalized": "역전할머니맥주경성대점",
            "category": "한식>주점",
            "address": "부산 남구 대연3동 50-2",
            "road_address": "부산 남구 수영로328번길 10",
            "phone": "051-628-0099",
            "lat": 35.1418,
            "lng": 129.0690,
            "distance_km": 0.5,
            "naver_link": "",
            "description": "생맥주 전문점",
            "crawled_data": {
                "visitor_review_count": 89,
                "blog_review_count": 32,
                "rating": "3.8",
                "keywords": ["생맥주", "안주 맛집"],
            },
            "source": "demo",
            "search_query": "경성대 맛집",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_005",
            "name": "깐부치킨 대연점",
            "name_normalized": "깐부치킨대연점",
            "category": "한식>치킨",
            "address": "부산 남구 대연동 88-5",
            "road_address": "부산 남구 용소로19번길 5",
            "phone": "051-634-5678",
            "lat": 35.1390,
            "lng": 129.0700,
            "distance_km": 0.8,
            "naver_link": "",
            "description": "바삭한 치킨 전문점",
            "crawled_data": {
                "visitor_review_count": 145,
                "blog_review_count": 55,
                "rating": "4.3",
                "keywords": ["바삭치킨", "야식"],
            },
            "source": "demo",
            "search_query": "경성대 치킨",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_006",
            "name": "백종원의원조쌈밥 경성대점",
            "name_normalized": "백종원의원조쌈밥경성대점",
            "category": "한식>쌈밥",
            "address": "부산 남구 대연3동 51-10",
            "road_address": "부산 남구 수영로 320",
            "phone": "051-627-3344",
            "lat": 35.1410,
            "lng": 129.0675,
            "distance_km": 0.4,
            "naver_link": "",
            "description": "한식 쌈밥 전문점",
            "crawled_data": {
                "visitor_review_count": 210,
                "blog_review_count": 78,
                "rating": "4.1",
                "keywords": ["쌈밥", "한식 맛집"],
            },
            "source": "demo",
            "search_query": "경성대 한식",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_007",
            "name": "이디야커피 경성대점",
            "name_normalized": "이디야커피경성대점",
            "category": "카페>커피전문점",
            "address": "부산 남구 대연3동 52-1",
            "road_address": "부산 남구 수영로 322",
            "phone": "051-625-1100",
            "lat": 35.1412,
            "lng": 129.0672,
            "distance_km": 0.3,
            "naver_link": "",
            "description": "커피 전문점",
            "crawled_data": {
                "visitor_review_count": 95,
                "blog_review_count": 28,
                "rating": "3.9",
                "keywords": ["아메리카노", "카공"],
            },
            "source": "demo",
            "search_query": "경성대 카페",
            "collected_at": datetime.now().isoformat(),
        },
        {
            "id": "rest_demo_008",
            "name": "오봉집 대연점",
            "name_normalized": "오봉집대연점",
            "category": "한식>감자탕",
            "address": "부산 남구 대연동 120-5",
            "road_address": "부산 남구 용소로 20",
            "phone": "051-636-7890",
            "lat": 35.1395,
            "lng": 129.0710,
            "distance_km": 0.9,
            "naver_link": "",
            "description": "감자탕 전문점",
            "crawled_data": {
                "visitor_review_count": 178,
                "blog_review_count": 62,
                "rating": "4.4",
                "keywords": ["감자탕", "뼈해장국"],
            },
            "source": "demo",
            "search_query": "경성대 한식",
            "collected_at": datetime.now().isoformat(),
        },
    ]

    return demo_restaurants


# ==============================================================================
# 수집기 메인 로직
# ==============================================================================

def collect_restaurants(test_mode=False):
    """
    네이버 Local Search API를 사용하여 학교 주변 음식점을 수집합니다.

    [수집 흐름]
    1. 지역 키워드 x 카테고리 조합으로 검색어 생성
       예: "경성대 한식", "대연동 일식" 등
    2. 각 검색어로 API 호출 → 결과 수집
    3. 카텍 좌표 → WGS84 변환
    4. 학교 기준 반경 10km 필터링
    5. 중복 제거 (정규화된 이름 + 주소 기준)
    6. restaurants_db.json에 저장

    Args:
        test_mode (bool): True이면 첫 번째 카테고리만 테스트
    """
    print("=" * 60)
    print(f"  음식점 데이터 수집기 v1.0")
    print(f"  학교: {config.SCHOOL_NAME}")
    print(f"  반경: {config.SEARCH_RADIUS_KM}km")
    print(f"  모드: {'데모' if config.DEMO_MODE else 'API'}")
    print("=" * 60)

    # --- 데모 모드: Mock 데이터 사용 ---
    if config.DEMO_MODE:
        all_restaurants = generate_demo_data()
        save_database(all_restaurants)
        return all_restaurants

    # --- API 모드: 실제 네이버 API 호출 ---
    all_restaurants = []
    seen_names = set()  # 중복 제거용

    # 카테고리 리스트 (테스트 모드면 1개만)
    categories = config.SEARCH_CATEGORIES[:1] if test_mode else config.SEARCH_CATEGORIES
    areas = config.SEARCH_AREA_KEYWORDS

    total_queries = len(areas) * len(categories)
    current_query = 0

    for area in areas:
        for category in categories:
            current_query += 1
            query = f"{area} {category}"
            print(f"\n[{current_query}/{total_queries}] 검색: '{query}'")

            # API 호출
            items = search_naver_local(
                query,
                display=config.NAVER_LOCAL_SEARCH_DISPLAY,
            )

            if items is None:
                print("  -> API 호출 실패, 건너뜀")
                continue

            if not items:
                print("  -> 결과 없음")
                continue

            print(f"  -> {len(items)}개 결과 수신")

            # 각 아이템 처리
            for item in items:
                processed = process_api_item(item, query)

                # 반경 필터링
                if not is_within_radius(
                    processed["lat"], processed["lng"],
                    config.SCHOOL_LAT, config.SCHOOL_LNG,
                    config.SEARCH_RADIUS_KM,
                ):
                    print(f"     [제외] {processed['name']} (반경 외: {format_distance(processed['distance_km'])})")
                    continue

                # 중복 체크 (정규화된 이름 기준)
                if processed["name_normalized"] in seen_names:
                    continue

                seen_names.add(processed["name_normalized"])
                all_restaurants.append(processed)
                print(f"     [수집] {processed['name']} ({processed['category']}) - {format_distance(processed['distance_km'])}")

            # API 호출 간 대기 (속도 제한 방지)
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  수집 완료: 총 {len(all_restaurants)}개 음식점")
    print(f"{'='*60}")

    # DB 저장
    save_database(all_restaurants)

    return all_restaurants


def save_database(restaurants):
    """
    수집된 음식점 데이터를 JSON 파일로 저장합니다.
    기존 DB가 있으면 병합(merge)합니다.
    """
    # data 디렉토리 생성
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # 기존 DB 로드 (있으면)
    existing_restaurants = []
    if os.path.exists(config.RESTAURANTS_DB_PATH):
        try:
            with open(config.RESTAURANTS_DB_PATH, "r", encoding="utf-8") as f:
                existing_db = json.load(f)
                existing_restaurants = existing_db.get("restaurants", [])
                print(f"\n[DB] 기존 데이터 {len(existing_restaurants)}건 로드")
        except (json.JSONDecodeError, KeyError):
            print("\n[DB] 기존 파일 파싱 실패, 새로 생성합니다.")

    # 기존 데이터와 병합 (중복 제거)
    existing_names = {r["name_normalized"] for r in existing_restaurants}
    new_count = 0
    for rest in restaurants:
        if rest["name_normalized"] not in existing_names:
            existing_restaurants.append(rest)
            existing_names.add(rest["name_normalized"])
            new_count += 1

    # DB 구조 생성
    db = {
        "metadata": {
            "school_name": config.SCHOOL_NAME,
            "school_lat": config.SCHOOL_LAT,
            "school_lng": config.SCHOOL_LNG,
            "radius_km": config.SEARCH_RADIUS_KM,
            "last_updated": datetime.now().isoformat(),
            "total_count": len(existing_restaurants),
        },
        "restaurants": existing_restaurants,
    }

    # JSON 파일 저장
    with open(config.RESTAURANTS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"[DB] 저장 완료: {config.RESTAURANTS_DB_PATH}")
    print(f"     신규 {new_count}건 추가 / 총 {len(existing_restaurants)}건")


# ==============================================================================
# 메인 실행부
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="네이버 음식점 데이터 수집기")
    parser.add_argument("--test", action="store_true", help="테스트 모드 (1개 카테고리만)")
    args = parser.parse_args()

    collect_restaurants(test_mode=args.test)

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
import urllib3

# IP 하드코딩 우회 시 발생하는 SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# 전역 세션(Session) 객체 생성 및 429 에러 자동 재시도 설정
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

api_session = requests.Session()
retry_strategy = Retry(
    total=10,
    backoff_factor=3.0,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
api_session.mount("https://", adapter)
api_session.mount("http://", adapter)

# Windows 콘솔 UTF-8 호환
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)


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
        "X-NCP-APIGW-API-KEY-ID": config.NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": config.NAVER_CLIENT_SECRET,
        "Host": "naverapihub.apigw.ntruss.com"
    }

    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": config.NAVER_LOCAL_SEARCH_SORT,
    }

    try:
        with api_session.get(
            config.NAVER_LOCAL_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=(5.0, 15.0),
            verify=False
        ) as response:
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])

    except requests.exceptions.HTTPError as e:
        print(f"  [API 오류] HTTP {response.status_code}: {e}")
        if response.status_code == 429:
            print("  -> Rate Limit 초과. 5초 대기 후 진행합니다.")
            time.sleep(5)
        elif response.status_code == 401:
            print("  -> API 키가 유효하지 않습니다. .env 파일을 확인하세요.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [네트워크 오류] {e}")
        return None

def search_naver_blog(query, display=2):
    headers = {
        "X-NCP-APIGW-API-KEY-ID": config.NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": config.NAVER_CLIENT_SECRET,
        "Host": "naverapihub.apigw.ntruss.com"
    }
    params = {"query": query, "display": display, "start": 1, "sort": "sim"}
    try:
        with api_session.get(config.NAVER_BLOG_SEARCH_URL, headers=headers, params=params, timeout=(3.0, 7.0), verify=False) as response:
            response.raise_for_status()
            return response.json().get("items", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            time.sleep(5)
        return []
    except:
        return []

def search_naver_image(query, display=1):
    headers = {
        "X-NCP-APIGW-API-KEY-ID": config.NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": config.NAVER_CLIENT_SECRET,
        "Host": "naverapihub.apigw.ntruss.com"
    }
    params = {"query": query, "display": display, "start": 1, "sort": "sim", "filter": "all"}
    try:
        with api_session.get(config.NAVER_IMAGE_SEARCH_URL, headers=headers, params=params, timeout=(3.0, 7.0), verify=False) as response:
            response.raise_for_status()
            return response.json().get("items", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            time.sleep(5)
        return []
    except:
        return []

def process_api_item(item, query, category_keyword=""):
    """
    네이버 Local Search API의 개별 응답 아이템을 정제하여
    통일된 형식의 딕셔너리로 변환합니다.
    """
    primary_category = "기타"
    if category_keyword:
        for primary, keywords in config.CATEGORY_MAPPING.items():
            if category_keyword in keywords:
                primary_category = primary
                break

    # 상호명에서 HTML 태그 제거
    name = clean_html_tags(item.get("title", ""))

    # 카텍 좌표 -> WGS84 위경도 변환
    lat, lng = katec_to_wgs84(item.get("mapx", 0), item.get("mapy", 0))

    # 학교로부터의 거리 계산
    distance = haversine_distance(
        lat, lng, config.SCHOOL_LAT, config.SCHOOL_LNG
    )

    # [핵심 성능 개선] 블로그/이미지 API를 호출하기 전에, 1km 반경 밖이면 즉시 버림! (API 낭비 방지)
    if not is_within_radius(lat, lng, config.SCHOOL_LAT, config.SCHOOL_LNG, config.SEARCH_RADIUS_KM):
        return None

    # 고유 ID 생성 (이름 + 주소 기반 해시)
    raw_id = f"{name}_{item.get('address', '')}"
    rest_id = "rest_" + hashlib.md5(raw_id.encode("utf-8")).hexdigest()[:8]

    # 블로그 리뷰는 사용자 요청으로 제외 (API 호출 속도 대폭 향상)
    print(f"     -> '{name}' 추가 정보(사진) 수집 중...")
    search_keyword = f"부경대 {name}"
    
    image_items = search_naver_image(search_keyword, display=1)
    blog_reviews = []

    image_url = ""
    if image_items:
        image_url = image_items[0].get("link", "")

    return {
        "id": rest_id,
        "name": name,
        "name_normalized": normalize_name(name),
        "category": primary_category,
        "address": item.get("address", ""),
        "road_address": item.get("roadAddress", ""),
        "phone": item.get("telephone", ""),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "distance_km": round(distance, 2),
        "naver_link": item.get("link", ""),
        "description": item.get("description", ""),
        "image_url": image_url,
        "blog_reviews": blog_reviews,
        "crawled_data": {
            "visitor_review_count": 0,
            "blog_review_count": len(blog_reviews),
            "rating": "N/A",
            "keywords": [],
        },
        "source": "naver_api_hub",
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

def save_chunk(data, chunk_index):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    file_path = os.path.join(config.DATA_DIR, f"restaurants_chunk_{chunk_index}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"restaurants": data}, f, ensure_ascii=False, indent=2)
        print(f"  [청크 저장] {file_path} (총 {len(data)}개)")
    except Exception as e:
        print(f"  [저장 실패] {e}")

def collect_restaurants(test_mode=False):
    print("=" * 60)
    print(f"  음식점 데이터 통합 수집기 (Local + Blog + Image)")
    print(f"  학교: {config.SCHOOL_NAME}")
    print(f"  반경: {config.SEARCH_RADIUS_KM}km")
    all_restaurants = []
    seen_names = set()
    # 기존 청크 데이터에서 seen_names 복원 (중복 방지)
    import glob
    for chunk_file in glob.glob(os.path.join(config.DATA_DIR, "restaurants_chunk_*.json")):
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data.get("restaurants", []):
                    seen_names.add(r.get("name_normalized", ""))
        except Exception:
            pass

    current_chunk_data = []
    
    # 1시간 전 150번째 쿼리에서 멈췄으므로 이어서 진행
    chunk_index = 3 
    CHUNK_SIZE = 50

    # 카테고리 리스트 (테스트 모드면 1개만)
    categories = config.SEARCH_CATEGORIES[:1] if test_mode else config.SEARCH_CATEGORIES
    areas = config.SEARCH_AREA_KEYWORDS

    total_categories = len(categories)
    total_queries = len(areas) * len(categories)
    current_query = 0

    for area in areas:
        for category in categories:
            current_query += 1
            if current_query < 794:
                continue
                
            query_str = f"{area} {category}".strip()
            print(f"\n[{current_query}/{total_queries}] 검색: '{query_str}'")

            # NCP API 허브는 로컬 검색 최대 결과 수가 5개로 제한되어 있으므로
            # 쓰레기 데이터가 슬롯을 차지하더라도 진짜 식당을 놓치지 않기 위해 20페이지(100개)까지 깊게 파고듭니다.
            for page in range(20):
                start = (page * 5) + 1
                items = search_naver_local(query_str, display=5, start=start)

                if items is None or not items:
                    break  # 더 이상 결과 없음

                for item in items:
                    # 1. 네이버가 응답한 실제 카테고리가 음식점/카페/간식 관련인지 확인하여 쓰레기 데이터(화장품, 복권 등) 원천 차단
                    api_category = item.get("category", "")
                    valid_categories = ["음식점", "카페", "주점", "간식", "베이커리", "패스트푸드", "뷔페"]
                    if not any(valid in api_category for valid in valid_categories):
                        continue

                    # 2. 중복 체크 (HTML 태그 제거 후 정규화)
                    raw_name = clean_html_tags(item.get("title", ""))
                    name_norm = normalize_name(raw_name)
                    if name_norm in seen_names:
                        continue
                        
                    seen_names.add(name_norm)

                    # category_keyword에는 suffix를 제외한 순수 category명만 전달
                    processed = process_api_item(item, query_str, category_keyword=category)

                    if processed is None:
                        continue  # 1km 반경 밖이므로 버림

                    current_chunk_data.append(processed)
                    all_restaurants.append(processed)
                    
                    # 100개 도달 시 청크 저장
                    if len(current_chunk_data) >= CHUNK_SIZE:
                        save_chunk(current_chunk_data, chunk_index)
                        chunk_index += 1
                        current_chunk_data = []

                # Rate Limit 대기
                time.sleep(0.3)

    # 남은 데이터 마지막 청크 저장
    if current_chunk_data:
        save_chunk(current_chunk_data, chunk_index)

    print(f"\n{'='*60}")
    print(f"  전체 수집 완료: 총 {len(all_restaurants)}개 음식점")
    print(f"{'='*60}")

    # 기존 단일 DB 파일(restaurants_db.json)에도 저장하여 웹 UI 호환성 유지
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

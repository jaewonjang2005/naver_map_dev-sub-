# -*- coding: utf-8 -*-
"""
config.py - 프로젝트 전역 설정값
=================================
API 키, 학교 좌표, 검색 반경 등 모든 설정을 한 곳에서 관리합니다.

[API 키 설정 방법]
1. 이 파일과 같은 디렉토리에 .env 파일을 생성합니다.
2. .env 파일에 아래 내용을 작성합니다:
   NAVER_CLIENT_ID=발급받은_클라이언트_ID
   NAVER_CLIENT_SECRET=발급받은_클라이언트_SECRET
   NCP_CLIENT_ID=네이버클라우드_클라이언트_ID
3. API 키가 없으면 DEMO_MODE=True로 Mock 데이터를 사용합니다.
"""

import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# ==============================================================================
# 네이버 검색 API (NAVER API HUB - NCP)
# - 용도: 지역(Local), 블로그, 이미지 검색
# ==============================================================================
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
DEMO_MODE = not bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)

# NCP API HUB 검색 엔드포인트
NAVER_LOCAL_SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/local"
NAVER_BLOG_SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
NAVER_IMAGE_SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/image"

# ==============================================================================
# 네이버 클라우드 플랫폼 Maps API (ncloud.com)
# - 용도: 웹 지도 표시 (JavaScript SDK)
# ==============================================================================
NCP_CLIENT_ID = os.getenv("NCP_CLIENT_ID", "")

# ==============================================================================
# 데모 모드 설정
# - API 키가 없으면 자동으로 데모 모드 활성화
# - 데모 모드에서는 Mock 데이터로 시스템을 테스트할 수 있음
# ==============================================================================
DEMO_MODE = not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)

# ==============================================================================
# 학교 정보 설정
# ==============================================================================
SCHOOL_NAME = "부경대학교"
SCHOOL_LAT = 35.1340802    # 위도 (latitude)
SCHOOL_LNG = 129.1031735   # 경도 (longitude)
SEARCH_RADIUS_KM = 0.7     # 검색 반경 (km) - 700m

# ==============================================================================
# 검색 카테고리 리스트
# - collector.py에서 이 카테고리들을 조합하여 검색합니다.
# - 예: "경성대 한식", "경성대 일식" 등
# ==============================================================================
SEARCH_CATEGORIES = [
    "맛집",
    "한식",
    "일식",
    "중식",
    "양식",
    "카페",
    "분식",
    "치킨",
    "피자",
    "햄버거",
    "고기",
    "해산물",
]

# 검색할 지역 키워드 (학교 주변 지역명)
SEARCH_AREA_KEYWORDS = [
    "부경대",
    "대연동",
    "못골",
    "남천동",
    "경성대"
]

# ==============================================================================
# 네이버 Local Search API 추가 설정
# ==============================================================================
NAVER_LOCAL_SEARCH_DISPLAY = 5   # 한 번에 가져올 결과 수 (최대 5)
NAVER_LOCAL_SEARCH_SORT = "comment"  # 정렬: random(랜덤), comment(리뷰순)

# ==============================================================================
# 파일 경로 설정
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WEB_DIR = os.path.join(BASE_DIR, "web")

RESTAURANTS_DB_PATH = os.path.join(DATA_DIR, "restaurants_db.json")
INPUT_FILE_PATH = os.path.join(DATA_DIR, "input_restaurants.txt")
MATCHED_RESULTS_PATH = os.path.join(DATA_DIR, "matched_results.json")

# ==============================================================================
# 업데이트 스케줄러 설정
# ==============================================================================
UPDATE_INTERVAL_HOURS = 24  # DB 갱신 주기 (시간)

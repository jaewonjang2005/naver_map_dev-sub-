import os
import sys
import time
import pandas as pd
import requests
import urllib3
import io

# Disable SSL warnings due to hardcoded IP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Windows console UTF-8 fix
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import config

# Setup Session with Retry
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


def map_api_category_to_custom(api_category_str):
    """
    네이버 API가 주는 카테고리 문자열(예: '음식점>한식>육류,고기요리')을
    우리의 CATEGORY_MAPPING에 맞춰 변환합니다.
    """
    if not api_category_str:
        return "기타"
        
    # 예: ['음식점', '한식', '육류,고기요리']
    parts = api_category_str.replace(" ", "").split(">")
    
    # 세부 카테고리(뒷부분)부터 우선 매핑 시도
    for part in reversed(parts):
        # part 안에 여러 단어가 있을 수 있음 (예: '육류,고기요리')
        sub_parts = part.split(",")
        for sub_part in sub_parts:
            for primary_cat, keywords in config.CATEGORY_MAPPING.items():
                if sub_part in keywords:
                    return primary_cat
                    
    # 매핑되지 않으면, 상위 카테고리라도 확인
    for part in parts:
        for primary_cat, keywords in config.CATEGORY_MAPPING.items():
            if part in keywords:
                return primary_cat

    return "기타"

def search_restaurant_category(name, address):
    """네이버 지역 검색 API로 식당 이름 검색 후 카테고리 반환"""
    # 동 이름 추출 (예: '부산 남구 대연동' -> '대연동')
    dong = ""
    if pd.notna(address) and isinstance(address, str):
        parts = address.split()
        for p in parts:
            if p.endswith("동"):
                dong = p
                break
                
    # 쿼리: 동 이름 + 식당 이름 (정확도 향상)
    query = f"{dong} {name}".strip()
    
    headers = {
        "X-NCP-APIGW-API-KEY-ID": config.NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": config.NAVER_CLIENT_SECRET,
        "Host": "naverapihub.apigw.ntruss.com"
    }

    params = {
        "query": query,
        "display": 1,
        "start": 1,
        "sort": "random",
    }

    try:
        response = api_session.get(
            config.NAVER_LOCAL_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=(5.0, 15.0),
            verify=False
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        
        if items:
            raw_category = items[0].get("category", "")
            mapped_category = map_api_category_to_custom(raw_category)
            return mapped_category, raw_category
            
    except Exception as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
            print("  [경고] 429 Rate Limit 도달! 10초 대기...")
            time.sleep(10)
    
    return None, None

def reclassify_csv():
    file_path = "merged_restaurants_result.csv"
    if not os.path.exists(file_path):
        print(f"[{file_path}] 파일이 없습니다.")
        return

    print("📁 CSV 파일을 불러옵니다...")
    df = pd.read_csv(file_path)
    
    # category가 '음식점' 이거나 비어있는 행 찾기
    mask = (df['category'] == '음식점') | (df['category'] == '') | df['category'].isna()
    target_indices = df[mask].index
    
    total = len(target_indices)
    print(f"🎯 재분류 대상 식당 수: {total}개")
    
    if total == 0:
        print("✅ 업데이트할 '음식점' 카테고리가 없습니다.")
        return
        
    updated_count = 0
    
    for i, idx in enumerate(target_indices):
        name = df.at[idx, 'name']
        address = df.at[idx, 'address']
        
        mapped_cat, raw_cat = search_restaurant_category(name, address)
        
        if mapped_cat:
            df.at[idx, 'category'] = mapped_cat
            updated_count += 1
            print(f"[{i+1}/{total}] '{name}' -> 원본: {raw_cat} -> 매핑: {mapped_cat}")
        else:
            print(f"[{i+1}/{total}] '{name}' -> ❌ 검색 실패 (또는 카테고리 없음)")
            
        time.sleep(0.1)  # 429 에러 방지
        
        # 100개마다 중간 저장
        if (i + 1) % 100 == 0:
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print("💾 중간 저장 완료")

    # 최종 저장
    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"\n🎉 재분류 완료! 총 {updated_count}개의 카테고리가 업데이트되었습니다.")
    print(f"결과 파일: {file_path}")

if __name__ == "__main__":
    reclassify_csv()

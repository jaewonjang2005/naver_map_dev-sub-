import pandas as pd
import time
import math
import random
import urllib.parse
import re
import os
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

KST = timezone(timedelta(hours=9))

def wgs84_to_epsg3857(lat, lon):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y

def extract_meters(text):
    if not text: return None
    km_match = re.search(r'([\d\.]+)\s*km', text, re.IGNORECASE)
    if km_match:
        return int(float(km_match.group(1)) * 1000)
    m_match = re.search(r'(\d+)\s*m', text, re.IGNORECASE)
    if m_match:
        return int(m_match.group(1))
    return None

def needs_distance(value):
    return pd.isna(value) or str(value).strip().lower() in {"", "nan", "none"}

def save_csv(df, path):
    """Avoid leaving a partial CSV if the process is interrupted mid-write."""
    temp_path = f"{path}.tmp"
    df.to_csv(temp_path, index=False, encoding='utf-8-sig')
    os.replace(temp_path, path)

def main():
    CSV_PATH = "최최종(거리,URL).csv"
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return
        
    df = pd.read_csv(CSV_PATH)
    
    # Ensure distance column exists and is string type
    if 'distance' not in df.columns:
        df['distance'] = ""
    if 'distance_status' not in df.columns:
        df['distance_status'] = ""
    if 'distance_checked_at' not in df.columns:
        df['distance_checked_at'] = ""

    # 1. 출발지: 부경대학교 대연캠퍼스
    start_lat, start_lon = 35.134080, 129.103173
    start_x, start_y = wgs84_to_epsg3857(start_lat, start_lon)
    start_name = urllib.parse.quote("부경대")
    
    # 한번에 처리할 최대 배치 사이즈 (차단 방지)
    MAX_BATCH_SIZE = 100
    processed_count = 0
    
    print(f"네이버 지도 도보 크롤링 시작 (최대 {MAX_BATCH_SIZE}개 배치)")
    print(f"출발지: 부경대 ({start_lat}, {start_lon})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        for idx, row in df.iterrows():
            if processed_count >= MAX_BATCH_SIZE:
                print(f"\n{MAX_BATCH_SIZE}개 처리 완료. 크롤러 휴식을 위해 종료합니다. 다음 실행 시 이어서 진행됩니다.")
                break
                
            dist_val = row.get('distance')
            if not needs_distance(dist_val):
                continue
                
            name = str(row['name'])
            
            if pd.isna(row.get('latitude')) or pd.isna(row.get('longitude')):
                print(f"[{processed_count+1}] {name} -> 좌표 누락 (건너뜀)")
                df.at[idx, 'distance'] = "좌표없음"
                df.at[idx, 'distance_status'] = "좌표없음"
                df.at[idx, 'distance_checked_at'] = datetime.now(KST).isoformat(timespec='seconds')
                processed_count += 1
                continue
                
            dest_lat = float(row['latitude'])
            dest_lon = float(row['longitude'])
            
            dest_x, dest_y = wgs84_to_epsg3857(dest_lat, dest_lon)
            dest_name = urllib.parse.quote(name)
            
            # 정확한 좌표계(EPSG:3857) URL 사용 -> 검색창/목록 없이 바로 경로 그려짐
            url = f"https://map.naver.com/p/directions/{start_x},{start_y},{start_name}/{dest_x},{dest_y},{dest_name}/-/walk"
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                
                # 네이버 경로 탐색 로딩 대기
                page.wait_for_timeout(2000)
                
                body_text = page.locator("body").inner_text()
                
                # 정규식 패턴 수정: "3분 214m", "15분 1.2km" 추출
                match = re.search(r'(\d+)\s*분\s*([\d\.]+(?:km|m))', body_text)
                
                if match:
                    dist_str = match.group(2)
                    dist_m = extract_meters(dist_str)
                    df.at[idx, 'distance'] = str(dist_m)
                    df.at[idx, 'distance_status'] = "측정완료"
                    df.at[idx, 'distance_checked_at'] = datetime.now(KST).isoformat(timespec='seconds')
                    print(f"[{processed_count+1}] {name}: {dist_m}m")
                    # 봇 차단 방지를 위해 랜덤 휴식 (4~7초)
                    time.sleep(random.uniform(4, 7))
                else:
                    # 도보 불가 혹은 텍스트 누락
                    df.at[idx, 'distance'] = "경로없음"
                    df.at[idx, 'distance_status'] = "도보경로없음"
                    df.at[idx, 'distance_checked_at'] = datetime.now(KST).isoformat(timespec='seconds')
                    print(f"[{processed_count+1}] {name} -> 경로없음")
                    
            except Exception as e:
                print(f"[{processed_count+1}] {name} -> Error: {e}")
                df.at[idx, 'distance'] = "에러"
                df.at[idx, 'distance_status'] = "크롤링오류"
                df.at[idx, 'distance_checked_at'] = datetime.now(KST).isoformat(timespec='seconds')
                
            processed_count += 1
            
            # 주기적으로 CSV 저장
            if processed_count % 10 == 0:
                save_csv(df, CSV_PATH)
                
        browser.close()
        
    save_csv(df, CSV_PATH)
    print("데이터 저장 완료!")

if __name__ == '__main__':
    main()

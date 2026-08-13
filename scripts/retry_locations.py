import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time
import urllib.parse
import math
from datetime import datetime, timezone, timedelta
import shutil
import sys
import subprocess

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def retry_locations():
    load_dotenv('.env')
    kakao_key = os.getenv('KAKAO_REST_API_KEY')
    if not kakao_key:
        print("Error: KAKAO_REST_API_KEY가 없습니다.")
        sys.exit(1)

    csv_path = '최최종(거리,URL).csv'
    KST = timezone(timedelta(hours=9))
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    backup = f"최최종(거리,URL).before_retry_{stamp}.csv"
    shutil.copy2(csv_path, backup)
    print(f"원본 백업 완료: {backup}")

    df = pd.read_csv(csv_path)
    
    # 대상: latitude 또는 longitude가 비어 있는 행 OR distance가 '경로없음'인 행
    target_mask = df['latitude'].isna() | df['longitude'].isna() | (df['distance'] == '경로없음')
    target_indices = df[target_mask].index

    print(f"총 재검색 대상 수: {len(target_indices)}개")
    if len(target_indices) == 0:
        print("대상 없음.")
        return

    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    BASE_LAT, BASE_LON = 35.133633, 129.104928
    
    report = []
    updated_indices = []

    def search_kakao(query):
        url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={urllib.parse.quote(query)}"
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            docs = res.json().get('documents', [])
            if docs:
                best = docs[0]
                return float(best['y']), float(best['x']), best['place_name'], best['address_name']
        except Exception as e:
            return None, None, None, str(e)
        return None, None, None, None

    for idx in target_indices:
        name = str(df.at[idx, 'name'])
        old_lat, old_lon = df.at[idx, 'latitude'], df.at[idx, 'longitude']
        
        queries = [
            f"부산 대연동 {name}",
            f"부경대 {name}",
            f"경성대 {name}",
            f"부산 남구 {name}"
        ]
        
        found = False
        for query in queries:
            lat, lon, cand_name, addr = search_kakao(query)
            if lat and lon:
                dist = haversine(BASE_LAT, BASE_LON, lat, lon)
                if '부산' in str(addr) and dist <= 1500:
                    df.at[idx, 'latitude'] = lat
                    df.at[idx, 'longitude'] = lon
                    df.at[idx, 'distance'] = None
                    report.append({
                        'id': df.at[idx, 'id'], 'name': name,
                        '기존좌표': f"{old_lat},{old_lon}", '새좌표': f"{lat},{lon}",
                        '검색어': query, '후보명': cand_name, '결과': '성공', '거리 재측정 결과': '', '오류': ''
                    })
                    updated_indices.append(idx)
                    found = True
                    break
            time.sleep(0.1)
            
        if not found:
            report.append({
                'id': df.at[idx, 'id'], 'name': name,
                '기존좌표': f"{old_lat},{old_lon}", '새좌표': '',
                '검색어': queries[-1], '후보명': '', '결과': '실패', '거리 재측정 결과': '', '오류': '검색결과없음/범위초과'
            })

    temp = csv_path + ".tmp"
    df.to_csv(temp, index=False, encoding="utf-8-sig")
    os.replace(temp, csv_path)

    if updated_indices:
        print(f"새 좌표를 찾은 {len(updated_indices)}개 식당에 대해 거리 크롤러를 1회 실행합니다...")
        try:
            subprocess.run(["python", "scripts/crawl_naver_walk.py"], check=True)
            df_re = pd.read_csv(csv_path)
            for r in report:
                if r['결과'] == '성공':
                    row_id = r['id']
                    match = df_re[df_re['id'] == row_id]
                    if not match.empty:
                        r['거리 재측정 결과'] = str(match['distance'].values[0])
        except Exception as e:
            print(f"크롤러 실행 중 오류: {e}")
            for r in report:
                if r['결과'] == '성공':
                    r['오류'] = str(e)
    
    report_df = pd.DataFrame(report)
    log_path = f"logs/location_retry_{stamp}.csv"
    os.makedirs("logs", exist_ok=True)
    report_df.to_csv(log_path, index=False, encoding="utf-8-sig")
    print(f"완료! 재검증 로그 저장됨: {log_path}")

if __name__ == "__main__":
    retry_locations()

import os
import re
import time
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
import pandas as pd
import subprocess
from duckduckgo_search import DDGS
import requests
from dotenv import load_dotenv

def ddg_retry():
    load_dotenv('.env')
    kakao_key = os.getenv('KAKAO_REST_API_KEY')
    if not kakao_key:
        print("Error: KAKAO_REST_API_KEY가 없습니다.")
        return

    csv_path = '최최종(거리,URL).csv'
    KST = timezone(timedelta(hours=9))
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    
    # 백업
    backup = f"최최종(거리,URL).before_ddg_{stamp}.csv"
    import shutil
    shutil.copy2(csv_path, backup)
    print(f"원본 백업 완료: {backup}")

    df = pd.read_csv(csv_path)
    
    # 기존에 잘 나온 것(거리값 숫자)은 건드리지 않음
    # 대상: distance가 '경로없음' 이거나 '좌표없음' 이거나 NaN인 행
    target_mask = df['distance'].isna() | (df['distance'] == '경로없음') | (df['distance'] == '좌표없음')
    target_indices = df[target_mask].index

    print(f"총 재검색 대상 수: {len(target_indices)}개")
    if len(target_indices) == 0:
        print("대상 없음.")
        return

    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    report = []
    updated_indices = []

    ddgs = DDGS()

    def get_coords_from_address(address):
        url = f"https://dapi.kakao.com/v2/local/search/address.json?query={urllib.parse.quote(address)}"
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            docs = res.json().get('documents', [])
            if docs:
                best = docs[0]
                return float(best['y']), float(best['x'])
        except Exception:
            pass
        return None, None

    # 주소 정규식 (주소: 부산 남구 수영로334번길 9)
    address_pattern = re.compile(r'주소\s*[:\s]?\s*(부산\s+[가-힣0-9\s-]+)', re.IGNORECASE)

    for i, idx in enumerate(target_indices, 1):
        name = str(df.at[idx, 'name'])
        query = f"부산 대연동 {name} 주소"
        print(f"[{i}/{len(target_indices)}] 검색 중: {name}")
        
        found_address = None
        lat, lon = None, None
        
        try:
            results = ddgs.text(query, region='kr-kr', max_results=5)
            for res in results:
                body = res.get('body', '')
                # 주소 패턴 찾기
                match = address_pattern.search(body)
                if match:
                    found_address = match.group(1).strip()
                    lat, lon = get_coords_from_address(found_address)
                    if lat and lon:
                        break
        except Exception as e:
            print(f"[{name}] 덕덕고 검색 에러: {e}")

        if lat and lon:
            df.at[idx, 'latitude'] = lat
            df.at[idx, 'longitude'] = lon
            df.at[idx, 'distance'] = None # 크롤러가 인식하도록 None으로
            report.append({
                'id': df.at[idx, 'id'], 'name': name,
                'found_address': found_address,
                'lat': lat, 'lon': lon, '결과': '성공'
            })
            updated_indices.append(idx)
            print(f"  -> 주소 발견: {found_address} ({lat}, {lon})")
        else:
            report.append({
                'id': df.at[idx, 'id'], 'name': name,
                'found_address': '', 'lat': '', 'lon': '', '결과': '실패'
            })
            print(f"  -> 실패")
            
        time.sleep(1) # DDG rate limit 방지

    # 원자적 저장
    temp = csv_path + ".tmp"
    df.to_csv(temp, index=False, encoding="utf-8-sig")
    os.replace(temp, csv_path)

    # 1회 거리 측정 (업데이트된 행만)
    if updated_indices:
        print(f"새 좌표를 찾은 {len(updated_indices)}개 식당에 대해 거리 크롤러를 실행합니다...")
        try:
            subprocess.run(["python", "scripts/crawl_naver_walk.py"], check=True)
            # 실행 후 다시 읽어서 측정 결과 확인 (검증)
            df_re = pd.read_csv(csv_path)
            for r in report:
                if r['결과'] == '성공':
                    row_id = r['id']
                    match = df_re[df_re['id'] == row_id]
                    if not match.empty:
                        r['최종_거리'] = str(match['distance'].values[0])
                        print(f"  -> {r['name']} 최종 측정 거리: {r['최종_거리']}")
        except Exception as e:
            print(f"크롤러 실행 중 오류: {e}")
    
    # 보고서 저장
    report_df = pd.DataFrame(report)
    log_path = f"logs/ddg_location_retry_{stamp}.csv"
    os.makedirs("logs", exist_ok=True)
    report_df.to_csv(log_path, index=False, encoding="utf-8-sig")
    print(f"\n작업 완료! DDG 우회 탐색 로그 저장됨: {log_path}")

if __name__ == "__main__":
    ddg_retry()

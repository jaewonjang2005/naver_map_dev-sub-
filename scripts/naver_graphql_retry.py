import os
import json
import asyncio
import urllib.parse
from datetime import datetime, timezone, timedelta
import pandas as pd
import subprocess
import shutil
from playwright.async_api import async_playwright

async def get_coords_from_naver(page, name):
    query = f"부산 남구 {name}"
    url = f"https://map.naver.com/v5/search/{urllib.parse.quote(query)}"
    
    coords = None
    
    async def handle_response(response):
        nonlocal coords
        if "search" in response.url or "allSearch" in response.url:
            try:
                text = await response.text()
                data = json.loads(text)
                if 'result' in data and 'place' in data['result'] and 'list' in data['result']['place']:
                    places = data['result']['place']['list']
                    if places:
                        first = places[0]
                        x_val = float(first.get('x', 0))
                        y_val = float(first.get('y', 0))
                        if 128 < x_val < 130 and 34 < y_val < 36:
                            coords = (y_val, x_val) # lat, lon
            except Exception:
                pass

    page.on("response", handle_response)
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=10000)
        await page.wait_for_timeout(3500)
    except Exception as e:
        pass
        
    page.remove_listener("response", handle_response)
    return coords

async def run_retry():
    csv_path = '최최종(거리,URL).csv'
    KST = timezone(timedelta(hours=9))
    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    
    backup = f"최최종(거리,URL).before_graphql_{stamp}.csv"
    shutil.copy2(csv_path, backup)
    print(f"원본 백업 완료: {backup}")

    df = pd.read_csv(csv_path)
    
    # 대상: distance가 '경로없음', '좌표없음', NaN 인 행 + 거리가 5000 초과인 이상치 방어
    target_mask = df['distance'].isna() | (df['distance'] == '경로없음') | (df['distance'] == '좌표없음')
    # 이상치(예: 14000)도 포함
    try:
        numeric_dist = pd.to_numeric(df['distance'], errors='coerce')
        outlier_mask = numeric_dist > 5000
        target_mask = target_mask | outlier_mask
    except:
        pass

    target_indices = df[target_mask].index

    print(f"총 재검색 대상 수: {len(target_indices)}개")
    if len(target_indices) == 0:
        print("대상 없음.")
        return

    report = []
    updated_indices = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for i, idx in enumerate(target_indices, 1):
            name = str(df.at[idx, 'name'])
            print(f"[{i}/{len(target_indices)}] 네이버 자체 검색 중: {name}")
            
            coords = await get_coords_from_naver(page, name)
            
            if coords:
                lat, lon = coords
                df.at[idx, 'latitude'] = lat
                df.at[idx, 'longitude'] = lon
                df.at[idx, 'distance'] = None # 크롤러가 인식하도록 None 처리
                report.append({
                    'id': df.at[idx, 'id'], 'name': name,
                    'lat': lat, 'lon': lon, '결과': '성공'
                })
                updated_indices.append(idx)
                print(f"  -> 좌표 발견 성공!: {lat}, {lon}")
            else:
                report.append({
                    'id': df.at[idx, 'id'], 'name': name,
                    'lat': '', 'lon': '', '결과': '실패'
                })
                print(f"  -> 실패 (네이버 지도에서도 검색 결과 없음)")
                
        await browser.close()

    temp = csv_path + ".tmp"
    df.to_csv(temp, index=False, encoding="utf-8-sig")
    os.replace(temp, csv_path)

    if updated_indices:
        print(f"새 좌표를 찾은 {len(updated_indices)}개 식당에 대해 거리 크롤러를 실행합니다...")
        try:
            subprocess.run(["python", "scripts/crawl_naver_walk.py"], check=True)
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
            
    report_df = pd.DataFrame(report)
    log_path = f"logs/naver_graphql_retry_{stamp}.csv"
    os.makedirs("logs", exist_ok=True)
    report_df.to_csv(log_path, index=False, encoding="utf-8-sig")
    print(f"\n작업 완료! API 탐색 로그 저장됨: {log_path}")

if __name__ == "__main__":
    asyncio.run(run_retry())

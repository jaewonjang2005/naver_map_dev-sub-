import pandas as pd
import requests
import os
import math
import concurrent.futures
from dotenv import load_dotenv
import time

load_dotenv()
NCP_CLIENT_ID = os.getenv('NCP_CLIENT_ID')
NCP_CLIENT_SECRET = os.getenv('NCP_CLIENT_SECRET')

PKNU_LON = 129.103986
PKNU_LAT = 35.133695

def haversine(lon1, lat1, lon2, lat2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
        
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance_km = R * c
    return int(distance_km * 1000) # Return in meters

def get_coordinates(address):
    url = f"https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query={address}"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NCP_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NCP_CLIENT_SECRET
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('addresses') and len(data['addresses']) > 0:
                return float(data['addresses'][0]['x']), float(data['addresses'][0]['y'])
    except Exception as e:
        pass
    return None, None

def process_row(name, address):
    dist = None
    if address:
        x, y = get_coordinates(address)
        if x and y:
            dist = haversine(PKNU_LON, PKNU_LAT, x, y)
    return name, dist

def main():
    print("Calculating straight-line (Haversine) distance from coordinates...")
    final_df = pd.read_csv('final_merged_data_with_images.csv', encoding='utf-8')
    
    naver_df = pd.read_csv('merged_restaurants_result.csv', encoding='utf-8')
    kakao_df = pd.read_csv('pknu_places_walk_15min.csv', encoding='utf-8')
    
    address_map = {}
    for _, row in naver_df.iterrows():
        addr = row.get('road_address') if pd.notna(row.get('road_address')) else row.get('address')
        if pd.notna(addr):
            address_map[row['name']] = addr
            
    for _, row in kakao_df.iterrows():
        addr = row.get('도로명 주소') if pd.notna(row.get('도로명 주소')) else row.get('지번 주소')
        if pd.notna(addr):
            address_map[row['가게 이름']] = addr
            
    inputs = []
    for _, row in final_df.iterrows():
        name = row['name']
        address = address_map.get(name)
        inputs.append((name, address))
        
    results = {}
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_name = {executor.submit(process_row, n, a): n for n, a in inputs}
        count = 0
        for future in concurrent.futures.as_completed(future_to_name):
            count += 1
            name, dist = future.result()
            results[name] = dist
            if count % 100 == 0:
                print(f"Processed {count}/{len(inputs)} items...")
                
    for index, row in final_df.iterrows():
        name = row['name']
        if name in results and results[name] is not None:
            final_df.at[index, 'distance'] = results[name]
            
    final_df.to_csv('final_merged_data_with_images.csv', index=False, encoding='utf-8-sig')
    print(f"Done in {time.time() - start_time:.2f}s!")

if __name__ == "__main__":
    main()

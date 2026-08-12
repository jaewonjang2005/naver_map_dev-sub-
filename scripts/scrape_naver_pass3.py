import pandas as pd
import requests
import math
import logging
import re
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = R * c
    return round(distance_km * 1000)

PKNU_LAT = 35.133693
PKNU_LON = 129.104987

csv_path = 'final_merged_data_with_images.csv'
df = pd.read_csv(csv_path)

missing_mask = df['distance'].isna()
missing_count = missing_mask.sum()
logging.info(f"Found {missing_count} rows with missing distance for PASS 3 (Naver Place).")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

count_updated = 0
count_failed = 0

for idx, row in df[missing_mask].iterrows():
    name = row['name']
    url = str(row.get('detail_url', ''))
    
    if not url.startswith('http'):
        count_failed += 1
        logging.warning(f"[FAIL] {name} -> No valid detail_url")
        continue

    try:
        res = requests.get(url, headers=headers, timeout=5)
        html = res.text
        
        # Look for "x":"129.100","y":"35.133" or similar in the HTML
        match = re.search(r'"x":"(12[0-9]\.[0-9]+)","y":"(3[0-9]\.[0-9]+)"', html)
        if not match:
            # Another format maybe
            match = re.search(r'longitude":"(12[0-9]\.[0-9]+)","latitude":"(3[0-9]\.[0-9]+)"', html)
        
        if match:
            lon = float(match.group(1))
            lat = float(match.group(2))
            
            dist_m = haversine(PKNU_LAT, PKNU_LON, lat, lon)
            df.at[idx, 'distance'] = dist_m
            count_updated += 1
            logging.info(f"[{count_updated}/{missing_count}] {name} (via Naver Place HTML) -> {dist_m}m")
        else:
            count_failed += 1
            logging.warning(f"[FAIL] {name} -> Could not find coords in HTML")
            
        time.sleep(0.5)
    except Exception as e:
        count_failed += 1
        logging.error(f"[ERROR] {name} -> {e}")

df.to_csv(csv_path, index=False, encoding='utf-8-sig')
logging.info(f"PASS 3 Done! Updated {count_updated}. Failed {count_failed}. Saved to {csv_path}")

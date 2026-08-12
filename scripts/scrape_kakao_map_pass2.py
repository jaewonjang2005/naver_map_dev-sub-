import pandas as pd
import requests
import time
import math
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Haversine distance calculation
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = R * c
    return round(distance_km * 1000) # Convert to meters and round

PKNU_LAT = 35.133693
PKNU_LON = 129.104987

csv_path = 'final_merged_data_with_images.csv'
df = pd.read_csv(csv_path)

missing_mask = df['distance'].isna()
missing_count = missing_mask.sum()
logging.info(f"Found {missing_count} rows with missing distance for PASS 2.")

headers = {
    'Referer': 'https://map.kakao.com/',
    'User-Agent': 'Mozilla/5.0'
}

count_updated = 0
count_failed = 0

def search_kakao(query):
    url = f"https://search.map.kakao.com/mapsearch/map.daum?q={query}&msFlag=A&sort=0"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json().get('place', [])
    except Exception as e:
        logging.error(f"Error querying {query}: {e}")
    return []

# Words to strip for fallback searches
stopwords = ['부경', '대연점', '경성대점', '경성대부경대점', '본점', '부산대연점', '부산경성대점', '직영점', '부산남구점']

for idx, row in df[missing_mask].iterrows():
    original_name = str(row['name'])
    
    # 1. Strip common suffixes
    clean_name = original_name
    for word in stopwords:
        clean_name = clean_name.replace(word, '').strip()
    
    queries_to_try = [
        f"부산 남구 {clean_name}", 
        f"대연동 {clean_name}",
        clean_name,
        original_name.split()[0] if len(original_name.split()) > 1 else None # Just the first word
    ]
    
    found = False
    
    for query in queries_to_try:
        if not query or len(query.strip()) < 2:
            continue
            
        places = search_kakao(query)
        time.sleep(0.3)
        
        for place in places:
            addr = place.get('address', '')
            # Verify it's actually in Busan (preferably Nam-gu or Suyeong-gu since it's near PKNU)
            if '부산' in addr and ('남구' in addr or '수영구' in addr):
                lon = float(place.get('lon', 0))
                lat = float(place.get('lat', 0))
                if lon > 0 and lat > 0:
                    dist_m = haversine(PKNU_LAT, PKNU_LON, lat, lon)
                    df.at[idx, 'distance'] = dist_m
                    count_updated += 1
                    logging.info(f"[{count_updated}/{missing_count}] {original_name} (found via '{query}') -> {dist_m}m")
                    found = True
                    break
        if found:
            break
            
    if not found:
        count_failed += 1
        logging.warning(f"[FAIL] {original_name} -> Could not find even with fallbacks.")

# Save back to CSV
df.to_csv(csv_path, index=False, encoding='utf-8-sig')
logging.info(f"PASS 2 Done! Updated {count_updated}. Failed {count_failed}. Saved to {csv_path}")

import pandas as pd
import requests
import time
import math
import logging

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

# Base coordinates (Pukyong National University)
PKNU_LAT = 35.133693
PKNU_LON = 129.104987

# Load the dataset
csv_path = 'final_merged_data_with_images.csv'
df = pd.read_csv(csv_path)

# Count how many distances are missing
missing_mask = df['distance'].isna()
missing_count = missing_mask.sum()
logging.info(f"Found {missing_count} rows with missing distance.")

headers = {
    'Referer': 'https://map.kakao.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

count_updated = 0
count_failed = 0

for idx, row in df[missing_mask].iterrows():
    name = str(row['name'])
    
    # Query Kakao Map internal search API
    url = f"https://search.map.kakao.com/mapsearch/map.daum?q={name}&msFlag=A&sort=0"
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'place' in data and len(data['place']) > 0:
                first_place = data['place'][0]
                lon = float(first_place.get('lon', 0))
                lat = float(first_place.get('lat', 0))
                
                if lon > 0 and lat > 0:
                    dist_m = haversine(PKNU_LAT, PKNU_LON, lat, lon)
                    df.at[idx, 'distance'] = dist_m
                    count_updated += 1
                    logging.info(f"[{count_updated}/{missing_count}] {name} -> {dist_m}m")
                else:
                    count_failed += 1
                    logging.warning(f"[{count_failed}] {name} -> No coordinates found in response.")
            else:
                count_failed += 1
                logging.warning(f"[{count_failed}] {name} -> No places found in response.")
        else:
            count_failed += 1
            logging.error(f"[{count_failed}] {name} -> API error {res.status_code}")
    except Exception as e:
        count_failed += 1
        logging.error(f"[{count_failed}] {name} -> Exception: {str(e)}")
        
    time.sleep(0.3) # Avoid hammering the API

# Save back to CSV
df.to_csv(csv_path, index=False, encoding='utf-8-sig')
logging.info(f"Done! Updated {count_updated} distances. Failed {count_failed}. Saved to {csv_path}")

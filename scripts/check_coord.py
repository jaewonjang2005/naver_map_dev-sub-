import pandas as pd
import requests
import json
import re

df = pd.read_csv('final_merged_data_with_images.csv', encoding='utf-8')
headers = {'User-Agent': 'Mozilla/5.0'}

for name in df['name'].head(5):
    url = f"https://m.place.naver.com/restaurant/list?query=부산 {name}"
    res = requests.get(url, headers=headers)
    match = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', res.text)
    if match:
        data = json.loads(match.group(1))
        place = None
        for k, v in data.items():
            if ('Place' in k or 'Restaurant' in k) and 'id' in v:
                place = v
                break
        if place:
            print(f"Name: {name} => x: {place.get('x')}, y: {place.get('y')}, coord: {place.get('coordinate')}, distance: {place.get('distance')}")

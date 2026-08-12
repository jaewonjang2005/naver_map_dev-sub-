import requests
import re
import json

url = "https://m.place.naver.com/restaurant/1586990780/home"
res = requests.get(url, headers={'User-Agent':'Mozilla/5.0'})
match = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', res.text)
if match:
    data = json.loads(match.group(1))
    with open('coord_output.txt', 'w', encoding='utf-8') as f:
        for k, v in data.items():
            if isinstance(v, dict) and 'x' in v and 'y' in v:
                f.write(f"{k} {v['x']} {v['y']}\n")

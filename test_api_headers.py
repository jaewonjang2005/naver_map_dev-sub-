import requests

def test_api(place_name):
    url = f"https://map.naver.com/v5/api/search?caller=pc_map&query={place_name}&type=all&displayCount=1&isPlaceRecommendationReplace=true&lang=ko"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://map.naver.com/v5/search/'
    }
    response = requests.get(url, headers=headers)
    print(f"[{place_name}] Status:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        try:
            place = data['result']['place']['list'][0]
            print("ID:", place.get('id'))
            print("Image:", place.get('thumUrl'))
            print("Detail:", f"https://m.place.naver.com/restaurant/{place.get('id')}")
        except:
            print("No result found.")

test_api("롤링파스타 부산경성대점")
test_api("물레방아즉석구이")

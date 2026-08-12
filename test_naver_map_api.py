import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}
url = "https://map.naver.com/p/api/search/allSearch?query=할리스 국립부경대청운관점&type=all"
response = requests.get(url, headers=headers)
print(response.status_code)
if response.status_code == 200:
    data = response.json()
    places = data.get('result', {}).get('place', {}).get('list', [])
    if places:
        print("ID:", places[0].get('id'))
        print("Name:", places[0].get('name'))

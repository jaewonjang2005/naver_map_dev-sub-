import requests
import os

client_id = "7yj1w2uuoc"
client_secret = "2vkdy2bTD6uPk4GbSt5kr9sZP8aJra649ZFm9TaD"

url = "https://openapi.naver.com/v1/search/image"
headers = {
    "X-Naver-Client-Id": client_id,
    "X-Naver-Client-Secret": client_secret
}
params = {
    "query": "할리스 국립부경대청운관점 음식",
    "display": 2
}

response = requests.get(url, headers=headers, params=params)
print(response.status_code)
print(response.json())

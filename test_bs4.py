import requests
from bs4 import BeautifulSoup
import re

def search_naver_web(place_name):
    query = f"부산 {place_name}"
    url = f"https://search.naver.com/search.naver?query={query}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None, None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to find place link
    # The place link usually looks like https://m.place.naver.com/restaurant/xxxx
    place_link = None
    for a in soup.find_all('a', href=True):
        if 'place.naver.com/restaurant/' in a['href']:
            place_link = a['href'].split('?')[0]
            break
            
    # Try to find image 
    # Usually images in the place snippet are from search.pstatic.net
    img_url = None
    # We can look for imgs near the place link or general pstatic images
    for img in soup.find_all('img', src=True):
        src = img['src']
        if 'search.pstatic.net' in src and 'type=f' in src: # often used for food/place
            img_url = src
            break
            
    # Fallback for image
    if not img_url:
        for img in soup.find_all('img', src=True):
            src = img['src']
            if 'pstatic.net' in src and 'data:image' not in src and 'icon' not in src and 'logo' not in src:
                img_url = src
                break

    return place_link, img_url

print(search_naver_web("롤링파스타 부산경성대점"))
print(search_naver_web("물레방아즉석구이"))

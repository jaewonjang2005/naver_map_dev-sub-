import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=400,800')
    options.add_argument('user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def get_images_for_place_fast(driver, wait, place_name):
    query = f"부산 {place_name}"
    search_url = f"https://m.place.naver.com/restaurant/list?query={query}"
    driver.get(search_url)
    
    try:
        # Wait until list item OR redirect home page header is found
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/restaurant/')] | //div[contains(@class, 'place_bluelink')] | //span[contains(text(), '거리뷰')]")))
    except:
        pass
    
    current_url = driver.current_url
    image_url = ""
    detail_url = ""
    
    if "/restaurant/" in current_url and "/list" not in current_url:
        detail_url = current_url.split("?")[0]
        try:
            img_el = driver.find_element(By.XPATH, "(//img[contains(@src, 'pstatic')])[1]")
            image_url = img_el.get_attribute("src")
        except:
            pass
    else:
        try:
            # First anchor that has restaurant in href
            first_a = driver.find_element(By.XPATH, "(//a[contains(@href, '/restaurant/')])[1]")
            detail_url = first_a.get_attribute("href").split("?")[0]
            
            # Find the image inside or nearby
            img_el = driver.find_element(By.XPATH, "(//img[contains(@src, 'pstatic')])[1]")
            image_url = img_el.get_attribute("src")
        except:
            pass
            
    # Fallback to pure place name search if not found
    if not detail_url:
        driver.get(f"https://m.place.naver.com/restaurant/list?query={place_name}")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/restaurant/')]")))
            current_url = driver.current_url
            if "/restaurant/" in current_url and "/list" not in current_url:
                detail_url = current_url.split("?")[0]
                img_el = driver.find_element(By.XPATH, "(//img[contains(@src, 'pstatic')])[1]")
                image_url = img_el.get_attribute("src")
            else:
                first_a = driver.find_element(By.XPATH, "(//a[contains(@href, '/restaurant/')])[1]")
                detail_url = first_a.get_attribute("href").split("?")[0]
                img_el = driver.find_element(By.XPATH, "(//img[contains(@src, 'pstatic')])[1]")
                image_url = img_el.get_attribute("src")
        except:
            pass

    return image_url, detail_url

def test_fast_crawler():
    print("Starting FAST crawler test on 5 items...")
    df = pd.read_csv('final_merged_data.csv', encoding='utf-8')
    test_df = df.head(5).copy()
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 3) # short wait
    
    try:
        for index, row in test_df.iterrows():
            place_name = row['name']
            print(f"Crawling: {place_name}")
            t1 = time.time()
            img, url = get_images_for_place_fast(driver, wait, place_name)
            t2 = time.time()
            
            print(f" -> Time: {t2-t1:.2f}s | Img: {img[:40]}... | URL: {url}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    test_fast_crawler()

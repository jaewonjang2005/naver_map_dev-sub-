import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=400,800')
    # Use Mobile User-Agent to ensure m.place.naver.com UI
    options.add_argument('user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def get_images_for_place(driver, wait, place_name):
    query = f"부산 {place_name}"
    search_url = f"https://m.place.naver.com/restaurant/list?query={query}"
    driver.get(search_url)
    time.sleep(3) # Increase wait time for search results to load
    
    current_url = driver.current_url
    place_id = None
    
    # Case 1: Redirected directly to the restaurant page
    if "/restaurant/" in current_url and "/list" not in current_url:
        try:
            place_id = current_url.split("/restaurant/")[1].split("/")[0]
        except IndexError:
            pass
    else:
        # Case 2: Show list of results, need to click the first one
        try:
            # Find the first item link
            # Mobile search results typically use an anchor with a specific class or structure. 
            # We will look for elements containing the place name text or generic block links.
            first_item = driver.find_element(By.XPATH, "//ul/li//a[contains(@href, '/restaurant/')] | //a[contains(@class, 'P7gyV')] | //div[contains(@class, 'place_bluelink')] | //a[contains(@href, 'place.naver.com/restaurant/')]")
            href = first_item.get_attribute("href")
            if href and "/restaurant/" in href:
                place_id = href.split("/restaurant/")[1].split("/")[0]
                place_id = place_id.split("?")[0]
            else:
                first_item.click()
                time.sleep(2)
                current_url = driver.current_url
                if "/restaurant/" in current_url:
                    place_id = current_url.split("/restaurant/")[1].split("/")[0]
        except Exception as e:
            # Try searching just the place_name
            driver.get(f"https://m.place.naver.com/restaurant/list?query={place_name}")
            time.sleep(3)
            current_url = driver.current_url
            if "/restaurant/" in current_url and "/list" not in current_url:
                try:
                    place_id = current_url.split("/restaurant/")[1].split("/")[0]
                except:
                    pass
            else:
                try:
                    first_item = driver.find_element(By.XPATH, "//ul/li//a[contains(@href, '/restaurant/')] | //a[contains(@class, 'P7gyV')] | //div[contains(@class, 'place_bluelink')] | //a[contains(@href, 'place.naver.com/restaurant/')]")
                    href = first_item.get_attribute("href")
                    if href and "/restaurant/" in href:
                        place_id = href.split("/restaurant/")[1].split("/")[0]
                        place_id = place_id.split("?")[0]
                    else:
                        first_item.click()
                        time.sleep(2)
                        current_url = driver.current_url
                        if "/restaurant/" in current_url:
                            place_id = current_url.split("/restaurant/")[1].split("/")[0]
                except Exception:
                    pass

    if not place_id:
        print(f"[{place_name}] Could not find place ID.")
        driver.save_screenshot(f"{place_name.replace(' ', '_')}_error.png")
        return []

    # Navigate to Photo tab
    photo_url = f"https://m.place.naver.com/restaurant/{place_id}/photo"
    driver.get(photo_url)
    time.sleep(2.5) # Wait for images to load
    
    food_images = []
    store_images = []
    
    def click_tab_by_text(texts):
        for t in texts:
            try:
                # Find tab containing the text
                tab = driver.find_element(By.XPATH, f"//a[@role='tab' or @role='button']//span[contains(text(), '{t}')]")
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(1.5)
                return True
            except:
                continue
        return False
        
    def extract_valid_images(limit=2):
        imgs = []
        try:
            # Find all images
            elements = driver.find_elements(By.XPATH, "//img[contains(@src, 'pstatic.net')]")
            for el in elements:
                src = el.get_attribute("src")
                # Exclude icons, favicons, logos, empty
                if src and "data:image" not in src and "icon" not in src and "logo" not in src:
                    # Naver uses thumbnail suffixes like ?type=w300, we can remove it or keep it. Let's keep it.
                    if src not in imgs:
                        imgs.append(src)
                if len(imgs) >= limit:
                    break
        except Exception:
            pass
        return imgs

    # Extract Food Images
    if click_tab_by_text(['음식', '메뉴']):
        food_images = extract_valid_images(limit=2)
        
    # Extract Store Images
    if click_tab_by_text(['매장', '외관', '내부']):
        store_images = extract_valid_images(limit=1)
        
    # Fallback if tabs weren't found or no images found
    if not food_images and not store_images:
        driver.get(photo_url) # reset
        time.sleep(2)
        all_imgs = extract_valid_images(limit=3)
        food_images = all_imgs[:2]
        store_images = all_imgs[2:3] if len(all_imgs) > 2 else []

    final_urls = food_images + store_images
    return final_urls

def crawl_all():
    print("Starting full crawler on all items...")
    input_file = 'final_merged_data.csv'
    output_file = 'final_merged_data_with_images.csv'
    
    # Check if we have a progress file to resume
    try:
        df = pd.read_csv(output_file, encoding='utf-8-sig')
        print(f"Resuming from {output_file}")
    except FileNotFoundError:
        df = pd.read_csv(input_file, encoding='utf-8')
    
    # Ensure image column is object to hold strings
    df['image'] = df['image'].astype(object)
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 5)
    
    save_interval = 10
    processed_count = 0
    
    try:
        for index, row in df.iterrows():
            # Skip if we already found images
            if pd.notna(row['image']) and str(row['image']).strip():
                continue
                
            place_name = row['name']
            print(f"[{index}/{len(df)}] Crawling: {place_name}")
            
            image_urls = get_images_for_place(driver, wait, place_name)
            
            image_str = ",".join(image_urls)
            df.at[index, 'image'] = image_str
            print(f" -> Found {len(image_urls)} images.")
            
            processed_count += 1
            if processed_count % save_interval == 0:
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"Progress saved at index {index}")
                
    except Exception as e:
        print("Crawler stopped unexpectedly:", e)
    finally:
        driver.quit()
        # Save final state
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"Finished crawling. Data saved to {output_file}.")

if __name__ == "__main__":
    crawl_all()

# -*- coding: utf-8 -*-
import sys
import io
import time
import re
import csv

# Windows 콘솔 UTF-8 출력 호환 설정
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import undetected_chromedriver as uc

def extract_numbers(text):
    if not text: return "0"
    numbers = re.findall(r"[\d,]+", text)
    return numbers[0].replace(",", "") if numbers else "0"

def scrape_all_naver_map_restaurants():
    queries = [
        "부경대 음식점", "부경대 맛집", "부경대 한식", "부경대 중식", 
        "부경대 일식", "부경대 양식", "부경대 아시안요리", "부경대 분식", 
        "부경대 고기집", "부경대 치킨", "부경대 피자", 
        "부경대 패스트푸드", "부경대 국밥", "부경대 술집", 
        "부경대 뷔페", "부경대 도시락"
    ]
    
    print("Chrome 브라우저를 엽니다. 잠시만 기다려주세요...")
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,800")
    options.add_argument("--user-data-dir=C:\\naver_map_cookie")
    # options.add_argument("--headless") # 필요시 주석 해제
    
    driver = uc.Chrome(options=options)
    
    restaurants = []
    seen_names = set() # 중복 수집 방지용 셋
    
    # 기존에 수집한 데이터가 있다면 불러와서 '이어하기' (프로그램 재시작 시 중복 방지)
    import os
    csv_filename = "pukyong_all_restaurants.csv"
    if os.path.exists(csv_filename):
        try:
            with open(csv_filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    restaurants.append(row)
                    seen_names.add(row.get('name', '이름 없음'))
            print(f"기존에 저장된 데이터 {len(seen_names)}개를 불러왔습니다! 이어서 수집을 시작합니다.")
        except Exception as e:
            print(f"기존 데이터 불러오기 실패: {e}")
            

    try:
        driver.get("https://map.naver.com/v5/")
        time.sleep(3)
        
        for query in queries:
            print(f"\n=========================================")
            print(f"[{query}] 검색 시작...")
            print(f"=========================================")
            
            # 검색어 입력
            try:
                driver.switch_to.default_content()
                # 안정적인 검색어 입력을 위해 여러 번 시도
                for attempt in range(3):
                    try:
                        search_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "input.input_search"))
                        )
                        search_input.send_keys(Keys.CONTROL + "a")
                        search_input.send_keys(Keys.DELETE)
                        time.sleep(0.5)
                        search_input.send_keys(query)
                        search_input.send_keys(Keys.ENTER)
                        break
                    except StaleElementReferenceException:
                        time.sleep(1)
                time.sleep(3)
            except Exception as e:
                print(f"[{query}] 검색창 처리 중 에러 발생: {e}")
                continue
            
            page_num = 1
            while True: # 페이지 루프
                print(f"--- {query} : {page_num} 페이지 수집 중 ---")
                driver.switch_to.default_content()
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchIframe")))
                    driver.switch_to.frame("searchIframe")
                except TimeoutException:
                    print("검색 결과가 없거나 로딩 지연. 다음 키워드로 넘어갑니다.")
                    break
                
                # 무한 스크롤로 50개 항목 모두 로딩
                try:
                    scroll_container = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#_pcmap_list_scroll_container"))
                    )
                    last_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                    scroll_attempts = 0
                    while scroll_attempts < 10:
                        driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", scroll_container)
                        time.sleep(1.5)
                        new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_container)
                        if new_height == last_height:
                            break
                        last_height = new_height
                        scroll_attempts += 1
                except Exception as e:
                    pass # 스크롤 컨테이너가 없는 경우(결과가 적을 때) 패스
                
                # 현재 로딩된 항목 가져오기
                items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS, li.CHC5F, li.VLTHu, li[data-laim-exp-id]")
                if not items:
                    print("더 이상 항목이 없습니다.")
                    break
                    
                print(f"현재 페이지에서 {len(items)}개의 식당을 발견했습니다.")
                
                for i in range(len(items)):
                    # 단일 항목 처리 시 발생하는 모든 에러를 방어하여 크롤러 중단 방지
                    try:
                        # 매 클릭 후 iframe이 풀릴 수 있으므로 다시 프레임 설정 및 요소 찾기
                        driver.switch_to.default_content()
                        driver.switch_to.frame("searchIframe")
                        
                        items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS, li.CHC5F, li.VLTHu, li[data-laim-exp-id]")
                        if i >= len(items): break
                        current_item = items[i]
                        
                        # 식당 이름만 미리 읽어서 중복 체크 (클릭 시간 단축)
                        name_elem = None
                        selectors = ["span.place_bluelink", "span.YwYLL", "a.tzwk0", "a.P7gyV", ".TYaxT", ".YwYLL"]
                        for sel in selectors:
                            try:
                                name_elem = current_item.find_element(By.CSS_SELECTOR, sel)
                                if name_elem: break
                            except NoSuchElementException:
                                continue
                        if not name_elem:
                            name_elem = current_item.find_element(By.TAG_NAME, "a")
                        
                        name = name_elem.text.strip()
                        if not name: name = "이름 없음"
                        
                        # 이미 수집한 식당이면 클릭 없이 패스 (핵심 로직)
                        if name in seen_names:
                            print(f"[SKIP] 이미 수집된 식당: {name}")
                            continue
                            
                        # 클릭해서 상세 정보 띄우기
                        driver.execute_script("arguments[0].click();", name_elem)
                        
                        # 2. entryIframe으로 스위치해서 상세 정보 읽기
                        driver.switch_to.default_content()
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "entryIframe")))
                        driver.switch_to.frame("entryIframe")
                            
                        # 데이터가 모두 로딩될 때까지 대기
                        time.sleep(2)
                        
                        try:
                            page_text = driver.find_element(By.TAG_NAME, "body").text
                        except:
                            continue
                        
                        # 카테고리 추출
                        try:
                            category = driver.find_element(By.CSS_SELECTOR, "span.DJJvD, span.lnJFt, span.LnRFH, span.GHAhO").text
                        except:
                            category = "음식점"
                            
                        # 주소 추출
                        address = "주소 없음"
                        addr_match = re.search(r'주소\n(.*?\n)', page_text)
                        if addr_match:
                            address = addr_match.group(1).strip()
                        elif "부산 " in page_text:
                            backup_match = re.search(r'(부산.*?)(?:\n|$)', page_text)
                            if backup_match:
                                address = backup_match.group(1).strip()
                            
                        # 별점 파싱
                        star_rating = "별점 없음"
                        star_match = re.search(r'별점\n?([0-9\.]+)', page_text)
                        if star_match:
                            star_rating = star_match.group(1)
                            
                        # 리뷰 파싱
                        visitor_reviews = "0"
                        blog_reviews = "0"
                        visit_match = re.search(r'방문자\s*리뷰\s*([0-9,]+)', page_text)
                        if visit_match:
                            visitor_reviews = visit_match.group(1)
                        else:
                            general_review_match = re.search(r'리뷰\s*([0-9,]+)', page_text)
                            if general_review_match:
                                visitor_reviews = general_review_match.group(1)
                            
                        blog_match = re.search(r'블로그\s*리뷰\s*([0-9,]+)', page_text)
                        if blog_match:
                            blog_reviews = blog_match.group(1)
                            
                        restaurants.append({
                            'name': name,
                            'category': category,
                            'star_rating': star_rating,
                            'visitor_reviews': visitor_reviews,
                            'blog_reviews': blog_reviews,
                            'address': address
                        })
                        seen_names.add(name) # 수집 완료 목록에 추가
                        print(f"수집 완료 ({len(seen_names)}째): {name} | 별점:{star_rating} | 리뷰:{visitor_reviews}")
                        
                    except Exception as e:
                        print(f"항목 처리 중 에러 발생 (스킵): {type(e).__name__}")
                        continue
                    
                # 페이지네이션(다음 페이지) 처리
                driver.switch_to.default_content()
                try:
                    driver.switch_to.frame("searchIframe")
                    # '다음페이지' 버튼 찾기
                    next_btns = driver.find_elements(By.XPATH, "//a[span[text()='다음페이지']]")
                    if next_btns:
                        next_btn = next_btns[0]
                        # 비활성화 상태(마지막 페이지)인지 확인
                        if next_btn.get_attribute("aria-disabled") == "true":
                            print(f"{query} 마지막 페이지 도달.")
                            break
                        else:
                            next_btn.click()
                            page_num += 1
                            time.sleep(3) # 페이지 넘김 후 로딩 대기
                    else:
                        break # 버튼이 없으면 끝
                except Exception as e:
                    print("다음 페이지 이동 중 에러:", type(e).__name__)
                    break

        return restaurants

    except Exception as e:
        print(f"크롤링 전체 에러 발생: {e}")
        return restaurants
        
    finally:
        driver.quit()

if __name__ == "__main__":
    result = scrape_all_naver_map_restaurants()
    
    print(f"\n[크롤링 완료] 중복을 제외하고 총 {len(result)}개의 식당 데이터를 수집했습니다!\n")
    
    # CSV 파일로 저장
    csv_filename = "pukyong_all_restaurants.csv"
    if result:
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'category', 'star_rating', 'visitor_reviews', 'blog_reviews', 'address'])
            writer.writeheader()
            writer.writerows(result)
        print(f"✅ 수집된 데이터가 '{csv_filename}' 파일로 저장되었습니다!")
    else:
        print("수집된 데이터가 없습니다.")

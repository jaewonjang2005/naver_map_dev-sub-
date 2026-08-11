# -*- coding: utf-8 -*-
"""entryIframe 심층 진단 - 실제 DOM 구조를 덤프하여 올바른 셀렉터를 찾습니다."""
import sys, io, time
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    driver.get("https://map.naver.com/v5/")
    time.sleep(5)

    search_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.input_search"))
    )
    search_input.send_keys("경성대 맛집")
    search_input.send_keys(Keys.ENTER)
    time.sleep(5)

    # searchIframe에서 첫 결과 클릭
    driver.switch_to.default_content()
    driver.switch_to.frame(driver.find_element(By.ID, "searchIframe"))
    time.sleep(2)

    items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS")
    if items:
        print(f"[검색 결과] {len(items)}개 발견, 첫 번째 클릭...")
        items[0].click()
    time.sleep(6)  # entryIframe 로딩을 충분히 대기

    # entryIframe으로 전환
    driver.switch_to.default_content()
    try:
        entry = driver.find_element(By.ID, "entryIframe")
        driver.switch_to.frame(entry)
    except Exception:
        print("[오류] entryIframe을 찾을 수 없음")
        driver.quit()
        sys.exit(1)

    time.sleep(3)

    # === 1) 텍스트가 있는 모든 주요 요소 덤프 ===
    print("\n" + "="*70)
    print("  entryIframe 내부 주요 요소 덤프")
    print("="*70)

    for tag in ["h1", "h2", "h3"]:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for e in elements:
            t = e.text.strip()
            if t:
                cls = e.get_attribute("class") or ""
                print(f"  <{tag} class='{cls}'> {t[:80]}")

    # === 2) span 중 텍스트 있는 것 (상호명/카테고리 후보) ===
    print("\n--- span 요소 (텍스트 있는 것, 상위 30개) ---")
    spans = driver.find_elements(By.TAG_NAME, "span")
    count = 0
    for s in spans:
        t = s.text.strip()
        if t and len(t) > 1 and count < 30:
            cls = s.get_attribute("class") or ""
            parent_tag = ""
            try:
                parent = s.find_element(By.XPATH, "..")
                parent_tag = parent.tag_name
                parent_cls = parent.get_attribute("class") or ""
            except:
                parent_cls = ""
            print(f"  <span class='{cls}'> (parent: {parent_tag}.{parent_cls[:30]}) -> '{t[:60]}'")
            count += 1

    # === 3) div 중 텍스트 있는 것 (주소/설명 후보) ===
    print("\n--- div 요소 (짧은 텍스트, 상위 20개) ---")
    divs = driver.find_elements(By.TAG_NAME, "div")
    count = 0
    for d in divs:
        t = d.text.strip()
        if t and 3 < len(t) < 100 and "\n" not in t and count < 20:
            cls = d.get_attribute("class") or ""
            print(f"  <div class='{cls[:40]}'> -> '{t[:80]}'")
            count += 1

    # === 4) a 태그 중 탭 관련 (리뷰/블로그) ===
    print("\n--- a 태그 (탭 영역) ---")
    links = driver.find_elements(By.TAG_NAME, "a")
    for a in links:
        t = a.text.strip()
        href = a.get_attribute("href") or ""
        if t and any(kw in t for kw in ["리뷰", "블로그", "사진", "메뉴", "홈", "소식"]):
            cls = a.get_attribute("class") or ""
            print(f"  <a class='{cls[:40]}' href='...{href[-30:]}'> -> '{t}'")

    print("\n[완료]")

finally:
    driver.quit()

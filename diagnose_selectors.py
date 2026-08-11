# -*- coding: utf-8 -*-
"""
네이버 지도 DOM 구조 진단 스크립트
- 검색 결과 iframe과 상세 iframe의 실제 CSS 클래스를 확인합니다.
"""

import sys
import io
import time

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
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # 1) 네이버 지도 접속 + 검색
    print("[1] 네이버 지도 접속...")
    driver.get("https://map.naver.com/v5/")
    time.sleep(5)

    print("[2] 검색어 입력: '경성대 맛집'")
    search_input = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.input_search"))
    )
    search_input.send_keys("경성대 맛집")
    search_input.send_keys(Keys.ENTER)
    time.sleep(5)

    # 2) iframe 목록 확인
    print("\n[3] 현재 페이지의 모든 iframe:")
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for i, iframe in enumerate(iframes):
        print(f"  iframe[{i}]: id='{iframe.get_attribute('id')}' name='{iframe.get_attribute('name')}' src='{(iframe.get_attribute('src') or '')[:80]}'")

    # 3) searchIframe 내부 구조 확인
    print("\n[4] searchIframe 내부 구조 탐색...")
    driver.switch_to.default_content()
    try:
        search_iframe = driver.find_element(By.ID, "searchIframe")
        driver.switch_to.frame(search_iframe)
        time.sleep(2)

        # li 태그들 확인
        all_li = driver.find_elements(By.TAG_NAME, "li")
        print(f"  총 <li> 태그 수: {len(all_li)}")

        # 클래스별 li 분석
        li_classes = {}
        for li in all_li:
            cls = li.get_attribute("class") or "(no class)"
            li_classes[cls] = li_classes.get(cls, 0) + 1
        print("  <li> 클래스별 분포:")
        for cls, count in sorted(li_classes.items(), key=lambda x: -x[1]):
            if count >= 2:
                print(f"    '{cls}': {count}개")

        # 검색 결과 항목 찾기 시도 (다양한 셀렉터)
        selectors_to_try = [
            "li.UEzoS", "li.CHC5F", "li[data-laim-exp-id]",
            "div.Ryr1F", "a.tzwk0", "a.P7gyV", "span.place_bluelink",
            "a.YwYLL", "span.YwYLL", "a[class*='name']",
            "div[class*='item']", "ul[class*='list'] > li",
        ]
        print("\n  검색 결과 셀렉터 탐색:")
        for sel in selectors_to_try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if elements:
                sample_text = elements[0].text[:50].replace("\n", " ") if elements[0].text else "(empty)"
                print(f"    [HIT] '{sel}': {len(elements)}개 -> '{sample_text}'")

        # 첫 번째 검색 결과 클릭 시도
        print("\n[5] 첫 번째 검색 결과 클릭 시도...")
        # 클릭 가능한 요소 찾기
        clickable_selectors = [
            "li.UEzoS", "li.CHC5F", "li[data-laim-exp-id]",
            "a.tzwk0", "a.P7gyV", "a.YwYLL",
        ]
        clicked = False
        for sel in clickable_selectors:
            items = driver.find_elements(By.CSS_SELECTOR, sel)
            if items:
                print(f"  '{sel}'로 클릭 시도 -> '{items[0].text[:30]}...'")
                items[0].click()
                clicked = True
                break

        if not clicked:
            # 아무 li라도 클릭
            for li in all_li:
                if li.text.strip() and len(li.text.strip()) > 5:
                    print(f"  일반 <li> 클릭 -> '{li.text[:30]}...'")
                    li.click()
                    clicked = True
                    break

        time.sleep(5)

    except Exception as e:
        print(f"  searchIframe 오류: {e}")

    # 4) entryIframe 내부 구조 확인
    print("\n[6] entryIframe 내부 구조 탐색...")
    driver.switch_to.default_content()
    try:
        entry_iframe = driver.find_element(By.ID, "entryIframe")
        driver.switch_to.frame(entry_iframe)
        time.sleep(2)

        # 상호명 후보 탐색
        name_selectors = [
            "span.GHAhO", "span.Fc1rA", "div.zD5Nm", "div.zD5Nm h2",
            "#_title", "#_title span", "span[class*='name']",
            "div.place_section h2", "div.O8qbU h2",
        ]
        print("  상호명 셀렉터 탐색:")
        for sel in name_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if elements:
                text = elements[0].text[:50] if elements[0].text else "(empty)"
                print(f"    [HIT] '{sel}': '{text}'")

        # 카테고리 후보 탐색
        cat_selectors = [
            "span.lnJFt", "span.DJJvD", "span[class*='category']",
            "span.LnRFH", "div.place_section span",
        ]
        print("  카테고리 셀렉터 탐색:")
        for sel in cat_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if elements:
                text = elements[0].text[:50] if elements[0].text else "(empty)"
                print(f"    [HIT] '{sel}': '{text}'")

        # 주소 후보 탐색
        addr_selectors = [
            "span.LDgIH", "span.jibun", "span[class*='addr']",
            "div.place_section_content span",
        ]
        print("  주소 셀렉터 탐색:")
        for sel in addr_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if elements:
                text = elements[0].text[:80] if elements[0].text else "(empty)"
                print(f"    [HIT] '{sel}': '{text}'")

        # 탭(리뷰/블로그) 영역 탐색
        tab_selectors = [
            "a[href*='review']", "a[href*='blog']",
            "span.PXMot", "[class*='tab'] a", "[role='tablist'] a",
            "div.dAsGb a", "div.flicking-camera a",
        ]
        print("  리뷰 탭 셀렉터 탐색:")
        for sel in tab_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            if elements:
                for elem in elements[:3]:
                    text = elem.text[:50] if elem.text else "(empty)"
                    if text and text != "(empty)":
                        print(f"    [HIT] '{sel}': '{text}'")

    except Exception as e:
        print(f"  entryIframe 오류: {e}")

    print("\n[완료] DOM 진단 종료")

finally:
    driver.quit()

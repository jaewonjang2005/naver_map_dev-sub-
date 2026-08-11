# -*- coding: utf-8 -*-
# ==============================================================================
# 네이버 지도 맛집 크롤러 (Naver Map Restaurant Crawler)
# ==============================================================================
#
# 이 스크립트는 네이버 지도(https://map.naver.com/)에서 맛집을 검색하고,
# 각 식당의 상세 정보를 수집하여 CSV 파일로 저장합니다.
#
# [실행 전 필수 패키지 설치]
# 터미널에서 아래 명령어를 실행하세요:
#
#   pip install selenium webdriver-manager pandas beautifulsoup4
#
# [사용법]
#   python naver_map_crawler.py
#
# ==============================================================================

import sys
import io
import time
import csv
import re
import os
from datetime import datetime

# --- Windows 콘솔 UTF-8 출력 호환 설정 ---
# cp949 인코딩에서 한글 특수문자 출력 오류를 방지합니다.
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# --- Selenium 관련 임포트 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

# --- WebDriverManager: 크롬 드라이버를 자동으로 설치/관리 ---
from webdriver_manager.chrome import ChromeDriverManager

# --- Pandas: 수집된 데이터를 DataFrame으로 정리하고 CSV로 저장 ---
import pandas as pd

# ==============================================================================
# 1. 설정값 (Configuration)
# ==============================================================================

# 테스트용 검색어 리스트 (에브리타임에서 추출한 맛집 리스트로 교체 가능)
SEARCH_QUERIES = [
    "부산 경성대 맛집",
    "사직동 햄버거",
]

# 검색어당 수집할 최대 식당 수 (너무 크면 시간이 오래 걸림)
MAX_RESTAURANTS_PER_QUERY = 5

# 각 단계별 대기 시간 (초) — 네트워크 상태에 따라 조절하세요
WAIT_SHORT = 1.5   # 짧은 대기 (요소 렌더링)
WAIT_MEDIUM = 3.0  # 중간 대기 (iframe 로딩)
WAIT_LONG = 5.0    # 긴 대기 (페이지 전체 로딩)

# WebDriverWait 최대 대기 시간 (초)
EXPLICIT_WAIT_TIMEOUT = 15

# 결과 CSV 파일명
OUTPUT_CSV = "naver_map_restaurants.csv"


# ==============================================================================
# 2. 크롬 드라이버 초기화
# ==============================================================================
def create_driver():
    """
    Chrome WebDriver를 생성하고 반환합니다.
    - headless 모드는 기본적으로 비활성화 (디버깅 용이)
    - 봇 탐지 우회를 위한 기본 옵션 설정
    """
    chrome_options = Options()

    # --- 봇 탐지 우회 기본 설정 ---
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # --- 브라우저 창 크기 설정 ---
    chrome_options.add_argument("--window-size=1920,1080")

    # --- User-Agent 설정 (일반 크롬 브라우저처럼 보이도록) ---
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # --- (선택) 헤드리스 모드: 아래 주석을 해제하면 브라우저 창이 표시되지 않음 ---
    # chrome_options.add_argument("--headless=new")

    # WebDriverManager가 현재 Chrome 버전에 맞는 드라이버를 자동 설치
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # navigator.webdriver 속성을 제거하여 봇 탐지 우회
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    return driver


# ==============================================================================
# 3. 헬퍼 함수들
# ==============================================================================

def safe_find_text(driver, by, selector, default="N/A"):
    """
    요소를 안전하게 찾아 텍스트를 반환합니다.
    요소가 없으면 default 값을 반환합니다.
    """
    try:
        element = driver.find_element(by, selector)
        text = element.text.strip()
        return text if text else default
    except (NoSuchElementException, StaleElementReferenceException):
        return default


def extract_review_count(text):
    """
    '리뷰 123' 또는 '123건' 같은 텍스트에서 숫자만 추출합니다.
    숫자가 없으면 '0'을 반환합니다.
    """
    if not text or text == "N/A":
        return "0"
    numbers = re.findall(r"[\d,]+", text)
    if numbers:
        return numbers[0].replace(",", "")
    return "0"


def wait_and_switch_to_iframe(driver, iframe_id, timeout=EXPLICIT_WAIT_TIMEOUT):
    """
    지정된 iframe이 로드될 때까지 대기한 후 전환합니다.

    [핵심 개념]
    네이버 지도는 두 개의 주요 iframe을 사용합니다:
      - 'searchIframe': 검색 결과 목록이 표시되는 영역
      - 'entryIframe': 개별 식당의 상세 정보가 표시되는 영역

    iframe 내부의 요소에 접근하려면 반드시 해당 iframe으로 전환해야 합니다.
    """
    try:
        # 먼저 기본 컨텍스트로 복귀 (중첩 iframe 방지)
        driver.switch_to.default_content()
        time.sleep(WAIT_SHORT)

        # iframe이 존재할 때까지 대기
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, iframe_id))
        )

        # iframe으로 전환
        iframe = driver.find_element(By.ID, iframe_id)
        driver.switch_to.frame(iframe)
        time.sleep(WAIT_SHORT)
        return True

    except TimeoutException:
        print(f"  [경고] iframe '{iframe_id}'을(를) 찾을 수 없습니다. (타임아웃)")
        return False
    except Exception as e:
        print(f"  [경고] iframe '{iframe_id}' 전환 중 오류: {e}")
        return False


# ==============================================================================
# 4. 검색 수행 함수
# ==============================================================================

def perform_search(driver, query):
    """
    네이버 지도에서 주어진 검색어를 입력하고 검색을 수행합니다.
    """
    print(f"\n{'='*60}")
    print(f"[검색] 검색어: '{query}'")
    print(f"{'='*60}")

    # 네이버 지도 메인 페이지로 이동
    driver.get("https://map.naver.com/v5/")
    time.sleep(WAIT_LONG)

    try:
        # 검색 입력창이 로드될 때까지 대기
        search_input = WebDriverWait(driver, EXPLICIT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input.input_search")
            )
        )

        # 기존 텍스트 초기화 후 검색어 입력
        search_input.clear()
        time.sleep(0.5)
        search_input.send_keys(query)
        time.sleep(0.5)

        # Enter 키로 검색 실행
        search_input.send_keys(Keys.ENTER)
        print(f"  [완료] 검색어 '{query}' 입력 완료")

        # 검색 결과 로딩 대기
        time.sleep(WAIT_LONG)
        return True

    except TimeoutException:
        print(f"  [실패] 검색 입력창을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"  [실패] 검색 중 오류 발생: {e}")
        return False


# ==============================================================================
# 5. 검색 결과 목록에서 식당 링크 수집
# ==============================================================================

def get_restaurant_elements(driver):
    """
    searchIframe 내의 검색 결과 목록에서 식당 요소들을 수집합니다.

    [iframe 전환 흐름]
    기본 컨텍스트 -> searchIframe 전환 -> 식당 목록 요소 수집
    """
    # searchIframe으로 전환
    if not wait_and_switch_to_iframe(driver, "searchIframe"):
        return []

    try:
        # 검색 결과 리스트가 로드될 때까지 대기
        WebDriverWait(driver, EXPLICIT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.UEzoS"))
        )
        time.sleep(WAIT_MEDIUM)

        # 모든 검색 결과 항목(li) 수집
        restaurant_items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS")
        print(f"  [목록] 검색 결과 {len(restaurant_items)}개 발견")
        return restaurant_items

    except TimeoutException:
        print("  [경고] 검색 결과 목록을 찾을 수 없습니다.")
        # 대체 셀렉터 시도
        try:
            restaurant_items = driver.find_elements(
                By.CSS_SELECTOR, "[class*='item']"
            )
            if restaurant_items:
                print(f"  [목록] 대체 셀렉터로 {len(restaurant_items)}개 발견")
                return restaurant_items
        except Exception:
            pass
        return []


# ==============================================================================
# 6. 개별 식당 상세 정보 추출
# ==============================================================================

def extract_restaurant_detail(driver, query):
    """
    entryIframe에서 개별 식당의 상세 정보를 추출합니다.

    [iframe 전환 흐름]
    기본 컨텍스트 -> entryIframe 전환 -> 상세 정보 파싱

    [수집 항목]
    1. 상호명        (식당 이름)
    2. 식당 주소      (도로명 또는 지번)
    3. 방문자 리뷰 수  (방문자가 직접 작성한 리뷰)
    4. 블로그 리뷰 수  (블로그 포스팅 수)
    5. 카테고리       (한식, 일식, 카페 등)
    """
    detail = {
        "검색어": query,
        "상호명": "N/A",
        "주소": "N/A",
        "방문자리뷰수": "0",
        "블로그리뷰수": "0",
        "카테고리": "N/A",
    }

    # entryIframe으로 전환
    if not wait_and_switch_to_iframe(driver, "entryIframe"):
        return detail

    try:
        # 상세 페이지가 로드될 때까지 충분히 대기
        time.sleep(WAIT_MEDIUM)

        # ----- (1) 상호명 추출 -----
        # 네이버 지도 상세 페이지의 식당 이름은 보통 상단의 큰 제목에 위치
        name_selectors = [
            "span.GHAhO",           # 일반적인 상호명 셀렉터
            "span.Fc1rA",           # 대체 셀렉터
            "div.zD5Nm h2",         # 또 다른 대체
            "#_title span",         # ID 기반
            "[class*='name']",      # 클래스에 name 포함
        ]
        for sel in name_selectors:
            name = safe_find_text(driver, By.CSS_SELECTOR, sel)
            if name != "N/A":
                detail["상호명"] = name
                break

        # ----- (2) 카테고리 추출 -----
        # 상호명 아래에 표시되는 업종/카테고리 정보
        category_selectors = [
            "span.lnJFt",           # 카테고리 텍스트
            "span.DJJvD",           # 대체 셀렉터
            "[class*='category']",  # 클래스에 category 포함
        ]
        for sel in category_selectors:
            category = safe_find_text(driver, By.CSS_SELECTOR, sel)
            if category != "N/A":
                detail["카테고리"] = category
                break

        # ----- (3) 주소 추출 -----
        # 식당의 도로명/지번 주소
        address_selectors = [
            "span.LDgIH",          # 주소 텍스트
            "span.jibun",          # 지번 주소
            "[class*='addr']",     # 클래스에 addr 포함
        ]
        for sel in address_selectors:
            address = safe_find_text(driver, By.CSS_SELECTOR, sel)
            if address != "N/A":
                detail["주소"] = address
                break

        # 주소를 직접 못 찾은 경우 -> 주소 복사 영역에서 시도
        if detail["주소"] == "N/A":
            try:
                # '주소' 라벨이 포함된 요소 근처에서 텍스트 추출 시도
                addr_elements = driver.find_elements(
                    By.CSS_SELECTOR, "[class*='place_section'] span"
                )
                for elem in addr_elements:
                    text = elem.text.strip()
                    # 주소 패턴: '부산' 또는 '서울' 등으로 시작하는 텍스트
                    if text and re.match(r"^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)", text):
                        detail["주소"] = text
                        break
            except Exception:
                pass

        # ----- (4) 방문자 리뷰 수 추출 -----
        visitor_review_selectors = [
            "a[href*='review'] span.PXMot",       # 방문자 리뷰 탭
            "a[href*='review'] em",                # 리뷰 수 강조
            "[class*='visitor'] span",             # 방문자 관련
            "span.PXMot",                          # 리뷰 카운트
        ]
        for sel in visitor_review_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    text = elem.text.strip()
                    if "방문자" in text or re.search(r"\d", text):
                        detail["방문자리뷰수"] = extract_review_count(text)
                        if detail["방문자리뷰수"] != "0":
                            break
                if detail["방문자리뷰수"] != "0":
                    break
            except Exception:
                continue

        # 탭 영역에서 리뷰 수를 한꺼번에 찾는 대체 방법
        if detail["방문자리뷰수"] == "0":
            try:
                tab_elements = driver.find_elements(
                    By.CSS_SELECTOR, "[class*='tab'] a, [role='tablist'] a"
                )
                for tab in tab_elements:
                    tab_text = tab.text.strip()
                    if "리뷰" in tab_text and "블로그" not in tab_text:
                        count = extract_review_count(tab_text)
                        if count != "0":
                            detail["방문자리뷰수"] = count
                            break
            except Exception:
                pass

        # ----- (5) 블로그 리뷰 수 추출 -----
        blog_review_selectors = [
            "a[href*='blog'] span.PXMot",          # 블로그 리뷰 탭
            "a[href*='blog'] em",                   # 블로그 리뷰 수 강조
        ]
        for sel in blog_review_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    text = elem.text.strip()
                    if "블로그" in text or re.search(r"\d", text):
                        detail["블로그리뷰수"] = extract_review_count(text)
                        if detail["블로그리뷰수"] != "0":
                            break
                if detail["블로그리뷰수"] != "0":
                    break
            except Exception:
                continue

        # 블로그 리뷰 대체 탐색
        if detail["블로그리뷰수"] == "0":
            try:
                tab_elements = driver.find_elements(
                    By.CSS_SELECTOR, "[class*='tab'] a, [role='tablist'] a"
                )
                for tab in tab_elements:
                    tab_text = tab.text.strip()
                    if "블로그" in tab_text:
                        count = extract_review_count(tab_text)
                        if count != "0":
                            detail["블로그리뷰수"] = count
                            break
            except Exception:
                pass

    except Exception as e:
        print(f"    [경고] 상세 정보 추출 중 오류: {e}")

    return detail


# ==============================================================================
# 7. 메인 크롤링 로직
# ==============================================================================

def crawl_restaurants(search_queries):
    """
    전체 크롤링 파이프라인을 실행합니다.

    [전체 흐름]
    1. Chrome 드라이버 생성
    2. 각 검색어에 대해:
       a. 네이버 지도에서 검색 수행
       b. searchIframe -> 검색 결과 목록 수집
       c. 각 식당 클릭 -> entryIframe -> 상세 정보 추출
       d. searchIframe으로 복귀 -> 다음 식당
    3. 전체 결과를 CSV로 저장
    """
    all_results = []  # 모든 수집 결과를 저장할 리스트
    driver = None

    try:
        # --- 드라이버 생성 ---
        print("[시작] 크롬 드라이버를 초기화합니다...")
        driver = create_driver()
        print("[완료] 드라이버 초기화 완료\n")

        # --- 각 검색어에 대해 반복 ---
        for query_idx, query in enumerate(search_queries, 1):
            print(f"\n[{query_idx}/{len(search_queries)}] 검색어 처리 중...")

            # (1) 검색 수행
            if not perform_search(driver, query):
                print(f"  [건너뜀] 검색 실패 -> 다음 검색어로 이동")
                continue

            # (2) searchIframe에서 검색 결과 목록 수집
            restaurant_items = get_restaurant_elements(driver)

            if not restaurant_items:
                print(f"  [건너뜀] 검색 결과 없음 -> 다음 검색어로 이동")
                continue

            # 수집할 식당 수 제한
            target_count = min(len(restaurant_items), MAX_RESTAURANTS_PER_QUERY)
            print(f"  [대상] 상위 {target_count}개 식당 정보를 수집합니다.\n")

            # (3) 각 식당에 대해 상세 정보 추출
            for i in range(target_count):
                print(f"  --- [{i+1}/{target_count}] 식당 처리 중 ---")

                try:
                    # * 매번 searchIframe으로 전환 (이전 식당 처리 후 컨텍스트가 변경되었으므로)
                    if not wait_and_switch_to_iframe(driver, "searchIframe"):
                        print(f"    [건너뜀] searchIframe 전환 실패 -> 다음 식당으로")
                        continue

                    time.sleep(WAIT_SHORT)

                    # 식당 목록을 다시 가져옴 (DOM이 갱신되었을 수 있으므로)
                    try:
                        current_items = driver.find_elements(
                            By.CSS_SELECTOR, "li.UEzoS"
                        )
                    except Exception:
                        current_items = driver.find_elements(
                            By.CSS_SELECTOR, "[class*='item']"
                        )

                    if i >= len(current_items):
                        print(f"    [건너뜀] 식당 인덱스 초과 -> 중단")
                        break

                    # * 식당 이름 링크를 클릭하여 상세 페이지로 이동
                    try:
                        # 식당 이름이 포함된 링크/span 요소를 클릭
                        clickable = current_items[i].find_element(
                            By.CSS_SELECTOR, "a.tzwk0, span.place_bluelink, a.P7gyV, a[class*='name']"
                        )
                        restaurant_name_preview = clickable.text.strip()
                        print(f"    [클릭] '{restaurant_name_preview}' 클릭...")
                        clickable.click()
                    except NoSuchElementException:
                        # 대체: li 요소 자체를 클릭
                        print(f"    [클릭] 식당 항목 클릭 (대체 방법)...")
                        current_items[i].click()

                    # 상세 페이지(entryIframe) 로딩 대기
                    time.sleep(WAIT_LONG)

                    # * entryIframe으로 전환하여 상세 정보 추출
                    detail = extract_restaurant_detail(driver, query)
                    all_results.append(detail)

                    # 수집 결과 미리보기 출력
                    print(f"    [수집완료] {detail['상호명']} | {detail['카테고리']}")
                    print(f"       주소: {detail['주소']}")
                    print(f"       방문자리뷰: {detail['방문자리뷰수']} | 블로그리뷰: {detail['블로그리뷰수']}")

                    # * 기본 컨텍스트로 복귀 (다음 반복을 위해)
                    driver.switch_to.default_content()
                    time.sleep(WAIT_SHORT)

                except StaleElementReferenceException:
                    print(f"    [경고] DOM 요소가 갱신됨 -> 다음 식당으로")
                    driver.switch_to.default_content()
                    continue
                except Exception as e:
                    print(f"    [경고] 식당 처리 중 오류: {e}")
                    driver.switch_to.default_content()
                    continue

            print(f"\n  [완료] '{query}' 검색어 처리 완료 ({len(all_results)}건 누적)")

    except WebDriverException as e:
        print(f"\n[오류] WebDriver 오류: {e}")
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자에 의해 중단되었습니다.")
    finally:
        # 드라이버 종료
        if driver:
            print("\n[종료] 드라이버를 종료합니다...")
            driver.quit()
            print("[완료] 드라이버 종료 완료")

    return all_results


# ==============================================================================
# 8. CSV 저장 함수
# ==============================================================================

def save_to_csv(results, filename=OUTPUT_CSV):
    """
    수집된 결과를 Pandas DataFrame으로 변환하여 CSV 파일로 저장합니다.
    - UTF-8 with BOM 인코딩 (엑셀에서 한글이 깨지지 않도록)
    """
    if not results:
        print("\n[경고] 수집된 데이터가 없어 CSV 파일을 생성하지 않습니다.")
        return None

    df = pd.DataFrame(results)

    # 컬럼 순서 정리
    column_order = ["검색어", "상호명", "카테고리", "주소", "방문자리뷰수", "블로그리뷰수"]
    existing_cols = [col for col in column_order if col in df.columns]
    df = df[existing_cols]

    # CSV 저장 (UTF-8 BOM -> 엑셀 호환)
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\n{'='*60}")
    print(f"[저장] CSV 파일 저장 완료: {output_path}")
    print(f"   총 {len(df)}건의 식당 정보가 저장되었습니다.")
    print(f"{'='*60}")

    # 수집 결과 요약 테이블 출력
    print("\n[결과] 수집 결과 요약:")
    print(df.to_string(index=False))

    return df


# ==============================================================================
# 9. 메인 실행부
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  네이버 지도 맛집 크롤러 v1.0")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  검색어 수: {len(SEARCH_QUERIES)}개")
    print(f"  검색어당 최대 수집: {MAX_RESTAURANTS_PER_QUERY}개")
    print("=" * 60)

    # 크롤링 실행
    results = crawl_restaurants(SEARCH_QUERIES)

    # CSV 저장
    save_to_csv(results)

    print("\n[완료] 크롤링이 완료되었습니다!")

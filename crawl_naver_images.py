import os
import time
import urllib.parse
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_top_one_image_url(page, store_name: str) -> str | None:
    """단순 가게 이름 검색 후 최상단 첫 번째 이미지 1개 URL 추출"""
    encoded_query = urllib.parse.quote(store_name)
    search_url = f"https://search.naver.com/search.naver?where=image&section=image&query={encoded_query}"

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=10000)

        # 이미지 요소가 로드될 때까지 최대 3초 대기
        page.wait_for_selector("img._fe_image_tab_content_thumbnail, img._image", timeout=3000)

        # 첫 번째 이미지 요소 가져오기
        first_img = page.query_selector("img._fe_image_tab_content_thumbnail, img._image")

        if first_img:
            src = first_img.get_attribute("src")
            if src and src.startswith("http"):
                return src

    except Exception as e:
        # 대기 시간 초과 등의 경우 2차 시도 (일반 img 태그 추출)
        try:
            images = page.query_selector_all("img")
            for img in images:
                src = img.get_attribute("src")
                if src and "search.pstatic.net" in src:
                    return src
        except Exception:
            pass

    return None


def insert_images_with_retry(image_data: dict, max_retries: int = 3):
    """Supabase Insert 재시도 로직"""
    for attempt in range(max_retries):
        try:
            supabase.table("store_images").insert(image_data).execute()
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise e


def check_existing_with_retry(store_id: int, max_retries: int = 3) -> bool:
    """DB 중복 스킵 체크"""
    for attempt in range(max_retries):
        try:
            res = (
                supabase.table("store_images")
                .select("id")
                .eq("store_id", store_id)
                .execute()
            )
            return len(res.data) > 0
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                return False


def run_naver_image_macro():
    res = supabase.table("stores").select("id, name").execute()
    stores = res.data

    print(f"총 {len(stores)}개 가게에 대해 단순 이름 검색 최상단 대표 이미지(1장) 수집을 시작합니다.\n")

    with sync_playwright() as p:
        # 헤드리스 브라우저 실행
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for store in stores:
            store_id = store["id"]
            store_name = store["name"]

            # 중복 체크
            if check_existing_with_retry(store_id):
                print(f"[{store_id}] {store_name}: 이미 등록되어 있어 스킵")
                continue

            # 최상단 대표 이미지 1장 추출
            image_url = get_top_one_image_url(page, store_name)

            if image_url:
                image_data = {
                    "store_id": store_id,
                    "image_url": image_url,
                    "is_main": True,
                }

                try:
                    insert_images_with_retry(image_data)
                    print(f"[{store_id}] {store_name} -> 대표 이미지 1개 저장 성공!")
                except Exception as e:
                    print(f"[{store_id}] {store_name} -> DB 저장 실패: {e}")
            else:
                print(f"[{store_id}] {store_name} -> 이미지를 찾지 못했습니다.")

            time.sleep(0.1)

        browser.close()

    print("\n모든 가게의 대표 이미지 1장 수집이 완료되었습니다.")


if __name__ == "__main__":
    run_naver_image_macro()
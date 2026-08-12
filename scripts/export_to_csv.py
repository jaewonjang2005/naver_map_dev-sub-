import os
import pandas as pd
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def export_table_to_csv(table_name: str, file_name: str):
    """Supabase 테이블 데이터를 전체 조회하여 CSV 파일로 저장"""
    try:
        print(f"[{table_name}] 테이블 데이터 불러오는 중...")

        # Supabase 기본 조회 제한(1,000개) 방지를 위해 range 지정하여 전체 데이터 수집
        all_data = []
        step = 1000
        start = 0

        while True:
            res = (
                supabase.table(table_name)
                .select("*")
                .range(start, start + step - 1)
                .execute()
            )
            data = res.data

            if not data:
                break

            all_data.extend(data)

            if len(data) < step:
                break

            start += step

        if all_data:
            df = pd.DataFrame(all_data)
            # 한글 깨짐 방지를 위해 utf-8-sig 인코딩 적용
            df.to_csv(file_name, index=False, encoding="utf-8-sig")
            print(
                f"✅ [{table_name}] -> '{file_name}' 저장 완료! (총 {len(df)}건)\n"
            )
        else:
            print(f"⚠️ [{table_name}] 테이블에 데이터가 없습니다.\n")

    except Exception as e:
        print(f"❌ [{table_name}] 추출 실패: {e}\n")


def run_export():
    # 1. 포스트(가게 정보) 테이블 CSV 추출
    export_table_to_csv("stores", "stores_data.csv")

    # 2. 이미지 테이블 CSV 추출
    export_table_to_csv("store_images", "store_images_data.csv")


if __name__ == "__main__":
    run_export()
import os
import math
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_value(val):
    """NaN, inf, 빈 문자열 등을 파이썬 None(JSON null)으로 변환"""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    val_str = str(val).strip()
    return val_str if val_str else None

def upload_data():
    # 1. CSV 로드
    df = pd.read_csv("final_merged_data.csv")

    stores_to_insert = []
    
    # 2. stores 데이터 가공 (모든 값을 clean_value 함수로 검증)
    for _, row in df.iterrows():
        stores_to_insert.append({
            "name": clean_value(row.get("name")),
            "category": clean_value(row.get("category")),
            "distance": clean_value(row.get("distance")),
            "detail_url": clean_value(row.get("detail_url"))
        })

    print(f"총 {len(stores_to_insert)}개 가게 데이터 업로드 시작...")

    # 3. stores 데이터 일괄 insert (또는 upsert)
    # returning='representation'으로 생성된 데이터와 id 반환받기
    res = supabase.table("stores").insert(stores_to_insert).execute()
    inserted_stores = res.data

    print(f"stores 테이블 업로드 완료 ({len(inserted_stores)}개)")

    # 4. store_images 데이터 가공 및 일괄 업로드
    images_to_insert = []
    for original_row, inserted_store in zip(df.to_dict(orient="records"), inserted_stores):
        img_url = clean_value(original_row.get("image"))
        if img_url:
            images_to_insert.append({
                "store_id": inserted_store["id"],
                "image_url": img_url,
                "is_main": True
            })

    if images_to_insert:
        supabase.table("store_images").insert(images_to_insert).execute()
        print(f"store_images 테이블 업로드 완료 ({len(images_to_insert)}개)")
    else:
        print("업로드할 이미지 데이터가 없습니다.")

if __name__ == "__main__":
    upload_data()
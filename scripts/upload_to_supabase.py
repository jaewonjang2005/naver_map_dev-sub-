import os
import json
import glob
import math
import pandas as pd
from supabase import create_client, Client

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_value(val):
    """NaN, NaT, Inf, -Inf 값을 JSON 호환 가능한 None(null)으로 변환하는 함수"""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
    return val

def load_and_process_data():
    # --------------------------------------
    # A. JSON 파일들 읽어서 데이터프레임 생성
    # --------------------------------------
    json_records = []
    json_files = glob.glob("data/restaurants_chunk_*.json")
    
    print(f"📂 발견된 JSON 파일: {len(json_files)}개")
    for file_path in json_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            items = data.get('restaurants', data) if isinstance(data, dict) else data
            json_records.extend(items)
            
    df_json = pd.DataFrame(json_records)
    
    # JSON 원본 필드 추출
    if 'crawled_data' in df_json.columns:
        df_json['visitor_reviews'] = df_json['crawled_data'].apply(
            lambda x: x.get('visitor_review_count') if isinstance(x, dict) else None
        )
        df_json['blog_reviews'] = df_json['crawled_data'].apply(
            lambda x: x.get('blog_review_count') if isinstance(x, dict) else None
        )
        df_json['star_rating'] = df_json['crawled_data'].apply(
            lambda x: x.get('rating') if isinstance(x, dict) else None
        )

    df_json['original_source'] = df_json.get('source', None)
    df_json['data_source'] = 'JSON'
    
    if 'distance_km' in df_json.columns:
        df_json['distance_m'] = df_json['distance_km'].apply(
            lambda x: float(x) * 1000 if pd.notna(x) and str(x).strip() != '' else None
        )
        
    if 'lat' in df_json.columns and 'latitude' not in df_json.columns:
        df_json['latitude'] = df_json['lat']
    if 'lng' in df_json.columns and 'longitude' not in df_json.columns:
        df_json['longitude'] = df_json['lng']

    # --------------------------------------
    # B. CSV 파일 읽어서 데이터프레임 생성
    # --------------------------------------
    csv_path = "pukyong_all_restaurants.csv"
    if os.path.exists(csv_path):
        print(f"📄 CSV 파일 불러오는 중: {csv_path}")
        df_csv = pd.read_csv(csv_path)
        df_csv['data_source'] = 'CSV'
    else:
        print("⚠️ CSV 파일을 찾을 수 없습니다. JSON 데이터만 진행합니다.")
        df_csv = pd.DataFrame()

    # --------------------------------------
    # C. 두 데이터 병합 (Outer Join)
    # --------------------------------------
    if not df_csv.empty and not df_json.empty:
        print("🔀 CSV와 JSON 데이터 병합 중 (가게 이름 'name' 기준)...")
        
        df_merged = pd.merge(df_csv, df_json, on='name', how='outer', suffixes=('_csv', '_json'))
        
        def determine_source(row):
            has_csv = pd.notna(row.get('data_source_csv'))
            has_json = pd.notna(row.get('data_source_json'))
            if has_csv and has_json:
                return 'MERGED'
            elif has_csv:
                return 'CSV'
            else:
                return 'JSON'
        
        df_merged['data_source'] = df_merged.apply(determine_source, axis=1)
        
        def combine_cols(csv_col, json_col, prefer_json=False):
            c_val = df_merged.get(csv_col) if csv_col in df_merged.columns else None
            j_val = df_merged.get(json_col) if json_col in df_merged.columns else None
            
            if prefer_json:
                return j_val.fillna(c_val) if j_val is not None and c_val is not None else (j_val if j_val is not None else c_val)
            else:
                return c_val.fillna(j_val) if c_val is not None and j_val is not None else (c_val if c_val is not None else j_val)

        # 컬럼 선택
        df_merged['category'] = combine_cols('category_csv', 'category_json', prefer_json=True)
        df_merged['star_rating'] = combine_cols('star_rating_csv', 'star_rating_json', prefer_json=False)
        df_merged['visitor_reviews'] = combine_cols('visitor_reviews_csv', 'visitor_reviews_json', prefer_json=False)
        df_merged['blog_reviews'] = combine_cols('blog_reviews_csv', 'blog_reviews_json', prefer_json=False)
        df_merged['address'] = combine_cols('address_csv', 'address_json', prefer_json=False)
        df_merged['road_address'] = combine_cols('road_address_csv', 'road_address_json', prefer_json=True)
        df_merged['latitude'] = combine_cols('latitude_csv', 'latitude_json', prefer_json=False)
        df_merged['longitude'] = combine_cols('longitude_csv', 'longitude_json', prefer_json=False)
        df_merged['distance_m'] = combine_cols('distance_m_csv', 'distance_m_json', prefer_json=False)
        df_merged['phone'] = combine_cols('phone_csv', 'phone_json', prefer_json=True)
        df_merged['image_url'] = df_merged.get('image_url_json', None)
        df_merged['original_source'] = df_merged.get('original_source_json', None)
        df_merged['collected_at'] = df_merged.get('collected_at_json', None)

    elif not df_json.empty:
        df_merged = df_json
    else:
        df_merged = df_csv

    # --------------------------------------
    # D. DB 테이블 컬럼과 매핑 및 완벽 정제
    # --------------------------------------
    target_columns = [
        'data_source', 'name', 'category', 'address', 'road_address', 
        'phone', 'latitude', 'longitude', 'distance_m', 
        'star_rating', 'visitor_reviews', 'blog_reviews', 
        'image_url', 'original_source', 'collected_at'
    ]
    
    for col in target_columns:
        if col not in df_merged.columns:
            df_merged[col] = None
            
    final_df = df_merged[target_columns].copy()
    
    # 숫자형 변환
    final_df['visitor_reviews'] = pd.to_numeric(final_df['visitor_reviews'], errors='coerce')
    final_df['blog_reviews'] = pd.to_numeric(final_df['blog_reviews'], errors='coerce')
    final_df['latitude'] = pd.to_numeric(final_df['latitude'], errors='coerce')
    final_df['longitude'] = pd.to_numeric(final_df['longitude'], errors='coerce')
    final_df['distance_m'] = pd.to_numeric(final_df['distance_m'], errors='coerce')
    
    # Dict 형태로 변환 후 순수 Python 값으로 엄격 정제 (NaN/Inf -> None 처리)
    raw_records = final_df.to_dict(orient='records')
    clean_records = []
    
    for record in raw_records:
        cleaned_record = {}
        for k, v in record.items():
            cleaned_record[k] = clean_value(v)
            # 정수형 컬럼 변환
            if k in ['visitor_reviews', 'blog_reviews'] and cleaned_record[k] is not None:
                cleaned_record[k] = int(cleaned_record[k])
        clean_records.append(cleaned_record)
        
    return clean_records

# ==========================================
# 3. Supabase 업로드 실행
# ==========================================
if __name__ == "__main__":
    records = load_and_process_data()
    print(f"🚀 총 {len(records)}개의 레코드를 Supabase에 업로드 준비 중...")
    
    chunk_size = 100
    for i in range(0, len(records), chunk_size):
        batch = records[i:i+chunk_size]
        try:
            response = supabase.table("restaurants").insert(batch).execute()
            print(f"✅ [{i+1} ~ {min(i+chunk_size, len(records))}] 개 완료")
        except Exception as e:
            print(f"❌ Error at batch {i}: {e}")

    print("🎉 جميع 작업을 성공적으로 마쳤습니다!")
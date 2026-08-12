import pandas as pd
import uuid
import random

def merge_datasets():
    # 1. Read merged_restaurants_result.csv (Naver Data)
    naver_df = pd.read_csv('merged_restaurants_result.csv', encoding='utf-8')
    # Use 'name' and 'category'
    naver_data = naver_df[['name', 'category']].copy()
    naver_data['distance'] = None

    # 2. Read pknu_places_walk_15min.csv (Kakao Data)
    kakao_df = pd.read_csv('pknu_places_walk_15min.csv', encoding='utf-8')
    kakao_data = kakao_df[['가게 이름', '검색 카테고리', '보행 거리(m)']].copy()
    kakao_data.rename(columns={
        '가게 이름': 'name',
        '검색 카테고리': 'category',
        '보행 거리(m)': 'distance'
    }, inplace=True)

    # 3. Combine both
    combined_df = pd.concat([naver_data, kakao_data], ignore_index=True)

    # 4. Remove duplicates by 'name'
    # Sort by distance so that when we drop duplicates, we keep the one with distance (if exists)
    # We can handle None vs float
    combined_df['has_dist'] = combined_df['distance'].notna()
    combined_df = combined_df.sort_values(by=['name', 'has_dist'], ascending=[True, False])
    
    # Drop duplicates by name
    combined_df = combined_df.drop_duplicates(subset=['name'], keep='first')
    combined_df = combined_df.drop(columns=['has_dist'])

    # 5. Add required columns: id, image, detail_url
    
    # Random but unique IDs
    # We can generate sequential numbers and shuffle them, or use unique random integers
    num_records = len(combined_df)
    ids = list(range(1, num_records + 1))
    random.shuffle(ids)
    
    combined_df['id'] = ids
    combined_df['image'] = ""
    combined_df['detail_url'] = ""

    # Reorder columns: id, name, category, image, distance, detail_url
    final_cols = ['id', 'name', 'category', 'image', 'distance', 'detail_url']
    combined_df = combined_df[final_cols]
    
    # Sort by ID or just leave as is. User didn't specify order, but sorting by ID makes sense
    combined_df = combined_df.sort_values(by='id')

    # Save to CSV
    combined_df.to_csv('final_merged_data.csv', index=False, encoding='utf-8-sig')
    print(f"Total merged unique places: {len(combined_df)}")
    print("Saved to final_merged_data.csv")

if __name__ == '__main__':
    merge_datasets()

import pandas as pd

naver_df = pd.read_csv('merged_restaurants_result.csv', encoding='utf-8')
kakao_df = pd.read_csv('pknu_places_walk_15min.csv', encoding='utf-8')

naver_has_image = naver_df['image_url'].notna().sum()
kakao_has_url = kakao_df['상세페이지 URL'].notna().sum()

print(f"Total Naver items: {len(naver_df)}, has image_url: {naver_has_image}")
print(f"Total Kakao items: {len(kakao_df)}, has detail url: {kakao_has_url}")

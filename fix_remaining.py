import pandas as pd
import config

file_path = "merged_restaurants_result.csv"
df = pd.read_csv(file_path)

mask = (df['category'] == '음식점')
target_indices = df[mask].index

print(f"Fixing {len(target_indices)} remaining restaurants...")

updated_count = 0

for idx in target_indices:
    name = str(df.at[idx, 'name'])
    
    # 1. 간단한 키워드 매칭
    mapped_cat = None
    for primary_cat, keywords in config.CATEGORY_MAPPING.items():
        for keyword in keywords:
            if keyword in name:
                mapped_cat = primary_cat
                break
        if mapped_cat:
            break
            
    # 2. 매칭 실패 시 '기타'로 강제 배정하여 '음식점' 없애기
    if not mapped_cat:
        mapped_cat = "기타"
        
    df.at[idx, 'category'] = mapped_cat
    updated_count += 1
    print(f"'{name}' -> {mapped_cat}")

df.to_csv(file_path, index=False, encoding='utf-8-sig')
print(f"\n✅ {updated_count}개 항목 처리 완료! 이제 '음식점' 카테고리는 모두 사라졌습니다.")

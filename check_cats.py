import pandas as pd
df = pd.read_csv('merged_restaurants_result.csv')
with open('cats.txt', 'w', encoding='utf-8') as f:
    for cat in sorted(df['category'].dropna().unique().tolist()):
        f.write(cat + '\n')

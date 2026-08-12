import pandas as pd
df = pd.read_csv('merged_restaurants_result.csv')
names = df[df['category'] == '기타']['name'].tolist()
with open('gita_names.txt', 'w', encoding='utf-8') as f:
    for n in names:
        f.write(str(n) + '\n')

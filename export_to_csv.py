import pandas as pd
from upload_to_supabase import load_and_process_data

if __name__ == "__main__":
    print("🔄 CSV 및 JSON 데이터 읽어오는 중...")
    records = load_and_process_data()
    
    # 1. 파이썬 Dict 리스트를 Pandas DataFrame으로 변환
    df = pd.DataFrame(records)
    
    # 2. CSV 파일로 저장 (한글 깨짐 방지를 위해 utf-8-sig 사용)
    output_filename = "merged_restaurants_result.csv"
    df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"🎉 성공적으로 추출되었습니다! 파일명: {output_filename}")
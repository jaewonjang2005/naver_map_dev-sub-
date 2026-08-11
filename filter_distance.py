import csv
import requests
import math
import re

# =================================================================
# 🔑 여기에 발급받으신 카카오 REST API 키를 문자열로 넣어주세요!
# 예: KAKAO_API_KEY = "1234abcd5678efgh9012ijkl3456mnop"
# =================================================================
KAKAO_API_KEY = "ff7cb10dd5871b6735ac4eef3de75929"

def clean_address(address):
    """
    카카오 주소 검색 API는 '1층', '103호', '건물명' 등이 붙어있으면 
    검색을 실패할 수 있으므로, 도로명/지번 주소 뒷부분을 적절히 잘라냅니다.
    """
    # ' 1층', ' 2층', ' B1', ' 103호' 등 층/호수 관련 단어가 나오면 그 앞까지만 사용
    cleaned = re.split(r'\s+\d+층|\s+[B지]\d+층|\s+\d+호|\s+[A-Z]동|\s+전층', address)[0]
    return cleaned.strip()

def get_lat_lng(address, api_key):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": clean_address(address)}
    
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            docs = res.json().get('documents')
            if docs:
                # x는 경도(longitude), y는 위도(latitude)
                return float(docs[0]['y']), float(docs[0]['x'])
    except Exception as e:
        print(f"API 요청 에러 ({address}): {e}")
    return None, None

def get_keyword_lat_lng(keyword, api_key):
    """키워드(예: '부경대학교 대연캠퍼스')로 위경도를 찾는 함수"""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": keyword}
    
    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        docs = res.json().get('documents')
        if docs:
            return float(docs[0]['y']), float(docs[0]['x'])
    return None, None

def haversine(lat1, lon1, lat2, lon2):
    """두 위경도 좌표 사이의 거리를 미터(m) 단위로 계산하는 하버사인 공식"""
    R = 6371000 # 지구의 평균 반지름 (미터)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c # 미터(m) 반환

def main():
    if KAKAO_API_KEY == "여기에_카카오_REST_API_키를_입력하세요":
        print("❌ 스크립트 상단의 KAKAO_API_KEY 에 카카오 API 키를 입력해주세요!")
        return
        
    input_csv = "pukyong_all_restaurants.csv"
    output_csv = "pukyong_restaurants_800m.csv"
    
    print("🏢 부경대학교 위경도 좌표를 조회 중...")
    pukyong_lat, pukyong_lng = get_keyword_lat_lng("부경대학교 대연캠퍼스", KAKAO_API_KEY)
    
    if not pukyong_lat:
        print("부경대학교 좌표를 찾을 수 없습니다. 기본 좌표(35.1335, 129.1058)를 사용합니다.")
        pukyong_lat, pukyong_lng = 35.1335, 129.1058
    else:
        print(f"부경대학교 좌표 확인 완료: 위도 {pukyong_lat}, 경도 {pukyong_lng}")
    
    filtered_restaurants = []
    
    # 원본 CSV 읽기
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    print(f"\n총 {len(rows)}개의 식당 주소 변환 및 거리 계산을 시작합니다...")
    
    success_count = 0
    fail_count = 0

    for i, row in enumerate(rows):
        address = row.get('address', '')
        if not address or address == "주소 없음":
            fail_count += 1
            continue
            
        lat, lng = get_lat_lng(address, KAKAO_API_KEY)
        
        if lat and lng:
            # 거리 계산
            distance = haversine(pukyong_lat, pukyong_lng, lat, lng)
            
            # 800m 이내인 경우에만 리스트에 추가
            if distance <= 800:
                # 기존 데이터에 위도, 경도, 거리 추가
                row['latitude'] = lat
                row['longitude'] = lng
                row['distance_m'] = round(distance, 1)
                filtered_restaurants.append(row)
            success_count += 1
        else:
            fail_count += 1
            
        if (i + 1) % 50 == 0:
            print(f"... {i+1} / {len(rows)} 개 처리 중 (현재 800m 이내: {len(filtered_restaurants)}개)")
            
    # 결과를 새로운 CSV로 저장
    if filtered_restaurants:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
            # 필드명 지정 (기존 + 위경도 + 거리)
            fieldnames = list(rows[0].keys()) + ['latitude', 'longitude', 'distance_m']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_restaurants)
            
        print(f"\n🎉 필터링 완료! 800m 이내 식당 총 {len(filtered_restaurants)}개가 '{output_csv}'에 저장되었습니다.")
        print(f"(좌표 변환 성공: {success_count}개, 실패: {fail_count}개)")
    else:
        print("\n800m 이내에 해당하는 식당이 없거나 변환에 실패했습니다.")

if __name__ == "__main__":
    main()

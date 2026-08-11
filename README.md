# 에브리타임 맛집 지도 파이프라인

에브리타임에서 추출한 맛집 리스트를 네이버 API와 매칭하여 네이버 지도 위에 시각화하는 자동화 파이프라인입니다.

## 🚀 주요 기능

1. **데이터 수집기 (`collector.py`)**
   - 네이버 Local Search API를 사용하여 특정 지역(예: 경성대학교 반경 10km)의 음식점 정보를 자동으로 수집하고 누적 저장합니다.
2. **매칭 엔진 (`matcher.py`)**
   - 에브리타임 등에서 수집한 텍스트 형태의 맛집 이름(`input_restaurants.txt`)을 로컬 DB와 지능적으로 매칭합니다.
   - 정확한 매칭, 부분 매칭을 지원하며, DB에 없을 시 실시간 API 검색을 통해 데이터를 찾아냅니다.
3. **웹 지도 시각화 (`web/index.html`)**
   - 네이버 클라우드 Maps API(JS v3)를 사용하여 매칭된 맛집을 다크 테마의 지도 위에 시각화합니다.
   - 카테고리별 마커 색상 구분, 상세 정보창, 필터링 기능을 제공합니다.
4. **자동 갱신 스케줄러 (`update_scheduler.py`)**
   - 백그라운드에서 주기적(기본 24시간)으로 수집기를 실행하여 최신 맛집 DB를 유지합니다.

## ⚙️ 설치 및 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 키를 입력합니다.
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`: [네이버 개발자센터](https://developers.naver.com)의 검색(Local) API 키
- `NCP_CLIENT_ID`: [네이버 클라우드 플랫폼](https://www.ncloud.com)의 Maps API(Web Dynamic Map) 키

```env
NAVER_CLIENT_ID=your_search_api_id
NAVER_CLIENT_SECRET=your_search_api_secret
NCP_CLIENT_ID=your_maps_api_id
```

### 3. 웹 지도용 키 교체
`web/index.html` 파일 내의 `YOUR_NCP_CLIENT_ID` 부분을 발급받은 Maps API 키로 교체합니다.

### 4. 실행 단계
```bash
# 1. 주변 맛집 데이터 수집 및 DB 업데이트
python collector.py

# 2. 에브리타임 리스트 매칭 실행
python matcher.py

# 3. 로컬 웹 서버 실행 (지도 시각화)
python -m http.server 8080 --directory web
# 이후 브라우저에서 http://localhost:8080 접속
```

## ⚠️ 이전 Selenium 크롤러 관련 안내
`naver_map_crawler.py`는 과거 사용되던 Selenium 기반 스크립트이나, 현재 네이버 지도의 강력한 안티봇 캡차(Captcha) 적용으로 인해 사용이 권장되지 않습니다. 공식 API 기반 파이프라인 사용을 권장합니다.

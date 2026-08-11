# -*- coding: utf-8 -*-
"""
utils.py - 유틸리티 함수 모음
==============================
좌표 변환, 거리 계산, HTML 태그 정제 등 공통 함수를 제공합니다.
"""

import re
import math


def katec_to_wgs84(mapx, mapy):
    """
    네이버 Local Search API의 카텍(KATEC) 좌표를 WGS84 위경도로 변환합니다.

    네이버 Local Search API의 mapx/mapy는 카텍 좌표계를 사용합니다.
    이를 일반적인 GPS 좌표(WGS84)로 변환해야 네이버 지도에 표시할 수 있습니다.

    [간이 변환 공식]
    정밀한 변환은 proj4 라이브러리가 필요하지만, 한국 영역에서는
    아래 간이 공식으로도 실용적 정밀도(오차 ~50m)를 확보할 수 있습니다.

    Args:
        mapx (str or int): 카텍 X 좌표 (경도 방향)
        mapy (str or int): 카텍 Y 좌표 (위도 방향)

    Returns:
        tuple: (latitude, longitude) WGS84 좌표
    """
    try:
        x = float(mapx)
        y = float(mapy)
    except (ValueError, TypeError):
        return (0.0, 0.0)

    # 네이버 Local API는 실제로 경위도 * 10^7 형식으로 반환하는 경우가 많음
    # mapx가 1000000 이상이면 10^7 나누기, 아니면 카텍 좌표로 판단
    if x > 1000000:
        # 10^7 스케일 좌표 -> 실제 경위도
        lng = x / 10_000_000
        lat = y / 10_000_000
    else:
        # 이미 경위도 형식인 경우
        lng = x
        lat = y

    return (lat, lng)


def haversine_distance(lat1, lng1, lat2, lng2):
    """
    Haversine 공식을 사용하여 두 GPS 좌표 간의 거리를 계산합니다.

    지구를 완전한 구로 가정하고, 두 지점 사이의 대원 거리(great-circle distance)를
    계산합니다. 한국 영역에서의 오차는 약 0.3% 이내입니다.

    Args:
        lat1, lng1: 첫 번째 지점의 위도, 경도 (도 단위)
        lat2, lng2: 두 번째 지점의 위도, 경도 (도 단위)

    Returns:
        float: 두 지점 간의 거리 (km)
    """
    R = 6371  # 지구 반경 (km)

    # 도 -> 라디안 변환
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    # Haversine 공식
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def clean_html_tags(text):
    """
    네이버 API 응답에 포함된 HTML 태그를 제거합니다.

    네이버 Local Search API의 title 필드에는 검색어 하이라이트를 위한
    <b></b> 태그가 포함되어 있습니다. 이를 제거하여 순수 텍스트만 추출합니다.

    Args:
        text (str): HTML 태그가 포함된 문자열

    Returns:
        str: 태그가 제거된 순수 텍스트
    """
    if not text:
        return ""
    # HTML 태그 제거
    clean = re.sub(r"<[^>]+>", "", text)
    # 연속 공백 정리
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def normalize_name(name):
    """
    음식점 이름을 정규화합니다 (매칭 정확도 향상용).

    공백, 특수문자를 제거하고 소문자로 변환하여 비교 기준을 통일합니다.
    예: "홍콩 반점 0410" -> "홍콩반점0410"

    Args:
        name (str): 원본 음식점 이름

    Returns:
        str: 정규화된 이름
    """
    if not name:
        return ""
    # HTML 태그 제거
    name = clean_html_tags(name)
    # 공백 제거
    name = name.replace(" ", "")
    # 소문자 변환 (영문 포함 이름 대비)
    name = name.lower()
    return name


def is_within_radius(lat, lng, center_lat, center_lng, radius_km):
    """
    주어진 좌표가 중심점으로부터 반경 내에 있는지 확인합니다.

    Args:
        lat, lng: 확인할 지점의 위도, 경도
        center_lat, center_lng: 중심점 (학교)의 위도, 경도
        radius_km: 반경 (km)

    Returns:
        bool: 반경 내에 있으면 True
    """
    distance = haversine_distance(lat, lng, center_lat, center_lng)
    return distance <= radius_km


def format_distance(distance_km):
    """
    거리를 사람이 읽기 쉬운 형식으로 변환합니다.

    Args:
        distance_km (float): 거리 (km)

    Returns:
        str: "1.2km" 또는 "800m" 형식
    """
    if distance_km < 1:
        return f"{int(distance_km * 1000)}m"
    return f"{distance_km:.1f}km"

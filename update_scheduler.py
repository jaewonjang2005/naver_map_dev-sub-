# -*- coding: utf-8 -*-
"""
update_scheduler.py - DB 자동 갱신 스케줄러
=============================================
정기적으로 collector.py를 실행하여 음식점 DB를 갱신합니다.

[사용법]
  python update_scheduler.py           # 백그라운드 실행 (24시간 주기)
  python update_scheduler.py --now     # 즉시 1회 실행
  python update_scheduler.py --hours 6 # 6시간 주기로 변경
"""

import sys
import io
import time
import argparse
from datetime import datetime

try:
    import schedule
except ImportError:
    print("[오류] schedule 패키지가 필요합니다: pip install schedule")
    sys.exit(1)

import config
from collector import collect_restaurants

# Windows 콘솔 UTF-8 호환
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def update_job():
    """스케줄러에 의해 호출되는 갱신 작업"""
    print(f"\n[스케줄러] 갱신 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        collect_restaurants(test_mode=False)
        print(f"[스케줄러] 갱신 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"[스케줄러] 갱신 중 오류 발생: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="음식점 DB 자동 갱신 스케줄러")
    parser.add_argument("--now", action="store_true", help="즉시 1회 실행")
    parser.add_argument(
        "--hours", type=int,
        default=config.UPDATE_INTERVAL_HOURS,
        help=f"갱신 주기 (시간, 기본: {config.UPDATE_INTERVAL_HOURS})",
    )
    args = parser.parse_args()

    if args.now:
        update_job()
    else:
        print(f"[스케줄러] {args.hours}시간마다 DB를 갱신합니다.")
        print(f"[스케줄러] 종료하려면 Ctrl+C를 누르세요.\n")

        schedule.every(args.hours).hours.do(update_job)

        # 시작 시 1회 즉시 실행
        update_job()

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 스케줄 체크
        except KeyboardInterrupt:
            print("\n[스케줄러] 종료되었습니다.")

"""운영 대시보드용 해결·종료 이력 적재 (변경 add-dashboard-history, 최신 목업 "운영 대시보드"·"내 실적").

운영진 데이터 4,000건 중 이미 해결·종료된 문의(팀 정답지 문의 제외)를 정답지 시각 그대로 svc에 재생한다. 접수 → 정보 요청 →
해결·종료까지의 실제 시각이 들어가므로 12개월 접수 추이, 해결 시각, 기한 충족률, 담당 상담원별 처리 실적을 실제 값으로 집계할 수 있다.
미해결 360건은 jobs/replay_demo.py가 이미 넣는다. 변환 방식(이력 이벤트, 메시지, SLA 목표)은 그 작업과 같다.

정답 열을 읽는다. CLAUDE.md 규칙 6의 예외를 **넓힌 것**이다: 조장 결정 2026-10-29(1안)은 미해결 360건 적재만 허락했다.
이 작업은 해결·종료 건까지 읽는다(최신 목업 기준 + 사용자 허락, 2026-10-31, 나중에 정리 보고). 서비스 실행 코드(backend/app)는
계속 gold.v_inputs만 읽는다. 시연 DB에 한 번 넣는 작업이다. 이미 svc에 있는 번호는 건너뛴다.

실행: 저장소 루트에서 python -m jobs.replay_history
"""

from __future__ import annotations

import psycopg

from app.config import get_settings
from jobs.replay_demo import replay

CLOSED = ("RESOLVED", "CLOSED")
BATCH = 250  # 한 트랜잭션에 넣는 건수(중간에 멈춰도 앞부분은 남고, 다시 돌리면 이어 넣는다)


def main() -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        target = skipped = added = 0
        while True:
            with conn.transaction():
                result = replay(conn, CLOSED, limit=BATCH)
            if added == 0:
                target, skipped = result["target"], result["skipped"]  # 처음 읽을 때의 값
            added += result["added"]
            print(f"  … {added}건 넣음", flush=True)
            if result["added"] == 0:
                break
        conn.execute("ANALYZE svc.ticket, svc.sub_ticket, svc.ticket_status_history, svc.ticket_message")
    print(f"해결·종료 {target}건 중 {added}건 넣음, {skipped}건은 이미 있었음")


if __name__ == "__main__":
    main()

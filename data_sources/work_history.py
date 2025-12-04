import logging
from typing import List, Optional, Dict, Any

try:
    from psycopg2.extras import RealDictCursor
except Exception:
    RealDictCursor = None  # Allow import without psycopg2 installed during tests

from db.connections import get_pg_conn
from data_sources.asset import asset_ds_instance as asset_ds

logger = logging.getLogger(__name__)

class WorkHistoryDataSource:
    """작업 이력(Postgres 'work_history' table) 조회. 실패 시 데모 반환."""

    def get_history_by_asset_name(self, asset_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        asset_id = asset_ds.get_asset_id_by_name(asset_name)
        if not asset_id:
            logger.warning("'%s' 자산 ID를 찾을 수 없어 WorkHistoryDataSource fallback 사용", asset_name)
        else:
            try:
                with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT work_date, worker_name, work_type, description
                        FROM work_history
                        WHERE asset_id = %s
                        ORDER BY work_date DESC
                        LIMIT %s
                        """,
                        (asset_id, limit),
                    )
                    rows = cur.fetchall()
                    if rows:
                        return [dict(row) for row in rows]
            except Exception as e:
                logger.warning("WorkHistoryDataSource fallback 사용 (%s)", e)

        return [
            {"work_date": "2024-05-20 10:00:00", "worker_name": "Admin", "work_type": "maintenance", "description": "정기 보안 패치 적용"},
            {"work_date": "2024-05-18 15:30:00", "worker_name": "Dev", "work_type": "update", "description": "애플리케이션 v1.2 배포"},
        ]

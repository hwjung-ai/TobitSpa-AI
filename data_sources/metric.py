import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

try:
    from psycopg2.extras import RealDictCursor
except Exception:
    RealDictCursor = None  # Allow import without psycopg2 installed during tests

from db.connections import get_pg_conn
from data_sources.asset import asset_ds_instance as asset_ds

logger = logging.getLogger(__name__)

class MetricDataSource:
    """메트릭(Timescale/Postgres) 조회. 실패 시 데모 반환."""

    def get_metric_timeseries(self, asset_name: str, metric: str, period: str = "1h"):
        asset_id = asset_ds.get_asset_id_by_name(asset_name)
        if not asset_id:
            logger.warning("'%s' 자산 ID를 찾을 수 없어 MetricDataSource fallback 사용", asset_name)
        else:
            try:
                with get_pg_conn() as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT ts, value
                        FROM metrics
                        WHERE asset_id = %s AND metric = %s AND ts >= now() - interval %s
                        ORDER BY ts
                        """,
                        (asset_id, metric, period),
                    )
                    rows = cur.fetchall()
                    if rows:
                        times = [r[0].strftime("%H:%M") for r in rows]
                        values = [r[1] for r in rows]
                        return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}
            except Exception as e:
                logger.warning("MetricDataSource fallback 사용 (%s)", e)

        # Fallback 로직: 동적 파라미터를 사용하여 데모 데이터 생성
        try:
            # '1h', '3 days' 같은 문자열에서 숫자와 단위를 분리
            num, unit = period.split()
            num = int(num)
            if 'hour' in unit:
                delta = timedelta(hours=num)
            elif 'day' in unit:
                delta = timedelta(days=num)
            elif 'minute' in unit:
                delta = timedelta(minutes=num)
            else:
                delta = timedelta(hours=1)
        except Exception:
            delta = timedelta(hours=1)

        now = datetime.now()
        times = [(now - delta + timedelta(minutes=i*10)).strftime("%H:%M") for i in range(6)]
        values = [random.randint(20, 100) for _ in range(6)]
        
        logger.info(f"Fallback metric data generated for {asset_name}, {metric}, {period}")
        return {"asset": asset_name, "metric": metric, "period": period, "times": times, "values": values}

import json
import logging
from typing import List, Optional, Dict, Any

try:
    from psycopg2.extras import RealDictCursor
except Exception:
    RealDictCursor = None  # Allow import without psycopg2 installed (tests use fallbacks)

from db.connections import get_pg_conn

logger = logging.getLogger(__name__)

class AssetDataSource:
    """자산 구성정보 (Postgres 'assets' table) 조회. 실패 시 데모 반환."""

    def get_asset_by_name(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """특정 이름의 자산 정보를 조회합니다."""
        demo = {
            "a812dpt": {"id": 1, "asset_type": "IT_DEVICE", "name": "a812dpt", "attributes": {"ip": "10.1.2.3", "os": "Linux", "ram": "16GB"}},
            "db-master": {"id": 2, "asset_type": "IT_DEVICE", "name": "db-master", "attributes": {"ip": "10.2.0.10", "os": "Linux", "ram": "64GB"}},
        }
        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, asset_type, name, attributes FROM assets WHERE lower(name) = lower(%s) LIMIT 1",
                    (asset_name,),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning("get_asset_by_name fallback 사용 (%s)", e)
        return demo.get(asset_name.lower())

    def find_assets_by_attributes(self, attrs: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """JSONB 속성을 기준으로 자산을 검색합니다."""
        if not attrs:
            return []
        
        demo_assets = [
            {"id": 1, "asset_type": "IT_DEVICE", "name": "a812dpt", "attributes": {"ip": "10.1.2.3", "os": "Linux", "ram": "16GB"}},
            {"id": 2, "asset_type": "IT_DEVICE", "name": "db-master", "attributes": {"ip": "10.2.0.10", "os": "Linux", "ram": "64GB"}},
            {"id": 3, "asset_type": "IT_DEVICE", "name": "web-01", "attributes": {"ip": "192.168.1.100", "os": "Ubuntu 22.04", "ram": "32GB"}},
        ]

        try:
            with get_pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                # JSONB containment operator @> 를 사용하여 쿼리
                cur.execute(
                    "SELECT id, asset_type, name, attributes FROM assets WHERE attributes @> %s::jsonb LIMIT %s",
                    (json.dumps(attrs), limit),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("find_assets_by_attributes fallback 사용 (%s)", e)
            
            # Fallback 로직: 데모 데이터에서 필터링
            results = []
            for asset in demo_assets:
                match = True
                for key, value in attrs.items():
                    if asset.get("attributes", {}).get(key) != value:
                        match = False
                        break
                if match:
                    results.append(asset)
            return results[:limit]

    def get_asset_id_by_name(self, asset_name: str) -> Optional[int]:
        asset = self.get_asset_by_name(asset_name)
        return asset.get("id") if asset else None

asset_ds_instance = AssetDataSource() # Renamed to avoid name clash if imported as `asset_ds`

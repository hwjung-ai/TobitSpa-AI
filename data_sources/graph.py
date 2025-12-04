import logging
from typing import List, Optional, Dict, Any

from db.connections import get_neo4j_driver

logger = logging.getLogger(__name__)

class GraphDataSource:
    """그래프 기반 연결성(Neo4j) 조회. 실패 시 데모 반환."""

    def _graph_to_dict(self, records):
        nodes = []
        edges = []
        node_ids = set()

        for record in records:
            for node in record.get('nodes', []):
                node_id = node.element_id
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    nodes.append({
                        "id": node.get('name'),
                        "label": node.get('name'),
                        "group": list(node.labels)[0],
                        "icon": node.get('icon', 'f1c0'), # fa-database
                        "color": node.get('color', '#6ca6fd')
                    })
            for rel in record.get('relationships', []):
                start_node_name = rel.start_node.get('name')
                end_node_name = rel.end_node.get('name')
                edges.append((start_node_name, end_node_name))
        
        return {"nodes": nodes, "edges": edges}

    def get_topology_for_asset(self, asset_name: str) -> Optional[Dict[str, Any]]:
        """특정 자산과 직접 연결된 이웃 노드들의 토폴로지 조회."""
        query = """
        MATCH (a:Asset {name: $asset_name})
        OPTIONAL MATCH (a)-[r]-(neighbor)
        RETURN nodes(collect(a) + collect(neighbor)) as nodes, relationships(collect(r)) as relationships
        """
        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                result = session.run(query, asset_name=asset_name)
                records = list(result)
                if records:
                    return self._graph_to_dict(records)
        except Exception as e:
            logger.warning("get_topology_for_asset fallback 사용 (%s)", e)
        
        # Fallback 데모 데이터
        return {
            "nodes": [
                {"id": "a812dpt", "label": "a812dpt", "icon": "f233", "color": "#f0ad4e"},
                {"id": "sw-core-01", "label": "sw-core-01", "icon": "f6ff", "color": "#5bc0de"},
                {"id": "nas-01", "label": "nas-01", "icon": "f0a0", "color": "#6ca6fd"}
            ],
            "edges": [("a812dpt", "sw-core-01"), ("a812dpt", "nas-01")]
        }

    def find_path_between_assets(self, start_asset: str, end_asset: str) -> Optional[Dict[str, Any]]:
        """두 자산 간의 최단 경로를 찾습니다."""
        query = """
        MATCH (start:Asset {name: $start_asset}), (end:Asset {name: $end_asset})
        MATCH p = allShortestPaths((start)-[*..5]-(end))
        RETURN nodes(p) as nodes, relationships(p) as relationships
        """
        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                result = session.run(query, start_asset=start_asset, end_asset=end_asset)
                records = list(result) # A single path becomes a single record
                if records:
                    return self._graph_to_dict(records)
        except Exception as e:
            logger.warning("find_path_between_assets fallback 사용 (%s)", e)

        # Fallback 데모 데이터
        if "a812dpt" in [start_asset, end_asset] and "db-master" in [start_asset, end_asset]:
             return {
                "nodes": [
                    {"id": "a812dpt", "label": "a812dpt", "icon": "f233", "color": "#f0ad4e"},
                    {"id": "sw-core-01", "label": "sw-core-01", "icon": "f6ff", "color": "#5bc0de"},
                    {"id": "db-master", "label": "db-master", "icon": "f1c0", "color": "#5cb85c"}
                ],
                "edges": [("a812dpt", "sw-core-01"), ("sw-core-01", "db-master")]
            }
        return None

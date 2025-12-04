import json
import os
import uuid
from typing import List, Optional, Dict, Any


DEFAULT_DATA = [
    {
        "id": "arch-root",
        "parent_id": None,
        "title": "Architecture",
        "type": "Architecture",
        "status": "Planned",
        "owner": "Infra",
        "due": "",
        "notes": "전체 아키텍처 구조를 작성합니다."
    },
    {
        "id": "arch-gateway",
        "parent_id": "arch-root",
        "title": "API Gateway",
        "type": "Architecture",
        "status": "In Progress",
        "owner": "BE",
        "due": "",
        "notes": "트래픽 관리, 인증/인가 적용."
    },
    {
        "id": "data-root",
        "parent_id": None,
        "title": "Data Ingestion",
        "type": "Data",
        "status": "Planned",
        "owner": "Data",
        "due": "",
        "notes": "로그/메트릭/이벤트 수집 파이프라인 정의."
    },
    {
        "id": "feature-root",
        "parent_id": None,
        "title": "Features",
        "type": "Feature",
        "status": "Planned",
        "owner": "PM",
        "due": "",
        "notes": "사용자 스토리/기능 목록."
    },
    {
        "id": "ui-root",
        "parent_id": None,
        "title": "UI",
        "type": "UI",
        "status": "Planned",
        "owner": "UX",
        "due": "",
        "notes": "SPA 화면 흐름과 스타일."
    },
    {
        "id": "schedule-root",
        "parent_id": None,
        "title": "Schedule",
        "type": "Schedule",
        "status": "Planned",
        "owner": "PM",
        "due": "",
        "notes": "마일스톤 및 일정."
    },
]


class PlannerStore:
    """간단한 JSON 기반 CRUD 저장소"""

    def __init__(self, path: str = os.path.join("assets", "planner.json")):
        self.path = path
        self._data: List[Dict[str, Any]] = []
        self._load()

    @staticmethod
    def _normalize_parent_id(value):
        """Tabulator selections may persist nested lists; flatten to a scalar or None."""
        while isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if value in ("", None, "null", "None"):
            return None
        if isinstance(value, str) and "Root" in value:
            return None
        return value

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                # 부모 ID를 항상 스칼라로 정규화해 dict/set 키 에러 방지
                changed = False
                ids = {item.get("id") for item in self._data}
                for item in self._data:
                    normalized = self._normalize_parent_id(item.get("parent_id"))
                    if normalized and normalized not in ids:
                        normalized = None
                    if normalized != item.get("parent_id"):
                        item["parent_id"] = normalized
                        changed = True
                    # ensure order field exists
                    if "order" not in item:
                        item["order"] = ""
                        changed = True
                if changed:
                    self._save()
            except Exception:
                self._data = DEFAULT_DATA.copy()
        else:
            self._data = DEFAULT_DATA.copy()
            # ensure order in defaults
            for item in self._data:
                item.setdefault("order", "")
            self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def list_items(self) -> List[Dict[str, Any]]:
        return list(self._data)

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        for item in self._data:
            if item["id"] == item_id:
                return dict(item)
        return None

    def add_item(self, parent_id: Optional[str], title: str, item_type: str,
                 status: str, owner: str, due: str, notes: str, order: str = "") -> Dict[str, Any]:
        new_item = {
            "id": uuid.uuid4().hex[:8],
            "parent_id": self._normalize_parent_id(parent_id),
            "title": title.strip() or "Untitled",
            "type": item_type,
            "status": status,
            "owner": owner,
            "due": due,
            "notes": notes,
            "order": str(order or "").strip(),
        }
        self._data.append(new_item)
        self._save()
        return new_item

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        for item in self._data:
            if item["id"] == item_id:
                normalized_updates = {
                    k: (self._normalize_parent_id(v) if k == "parent_id" else (str(v).strip() if k == "order" else v))
                    for k, v in updates.items()
                    if v is not None
                }
                item.update(normalized_updates)
                self._save()
                return True
        return False

    def delete_item(self, item_id: str):
        # 자식도 함께 제거
        to_delete = {item_id}
        changed = True
        while changed:
            changed = False
            for item in list(self._data):
                if item["parent_id"] in to_delete and item["id"] not in to_delete:
                    to_delete.add(item["id"])
                    changed = True
        self._data = [i for i in self._data if i["id"] not in to_delete]
        self._save()

    def _build_tree(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        nodes = []
        for item in self._data:
            if item.get("parent_id") == parent_id:
                child = dict(item)
                children = self._build_tree(child["id"])
                if children:
                    child["_children"] = children
            nodes.append(child)
        # 정렬: order(숫자 우선) -> title
        def _order_key(item):
            val = item.get("order", "")
            try:
                return (0, int(val))
            except Exception:
                return (1, str(val))
        nodes.sort(key=lambda x: (_order_key(x), x.get("title", "")))
        return nodes

    def to_tree_rows(self) -> List[Dict[str, Any]]:
        """Tabulator dataTree에서 사용할 형태(_children 포함)로 변환"""
        return self._build_tree(None)

    def _get_descendants(self, parent_id: Optional[str]) -> set:
        """재귀적으로 모든 자손 ID를 찾습니다."""
        # parent_id가 리스트일 수 있는 경우를 대비하여 첫 번째 요소 사용
        if isinstance(parent_id, (list, tuple)):
            parent_id = parent_id[0] if parent_id else None
        
        if not parent_id or not isinstance(parent_id, str):
            return set()

        descendants = set()
        children_to_check = [item["id"] for item in self._data if item.get("parent_id") == parent_id]

        for child_id in children_to_check:
            descendants.add(child_id)
            descendants.update(self._get_descendants(child_id))

        return descendants

    def parent_options(self, exclude_id: Optional[str] = None) -> List[tuple]:
        """부모로 선택 가능한 옵션을 계층 구조로 반환합니다."""
        opts = [("최상위 (Root)", None)]
        
        items_to_render = self._data
        if exclude_id:
            if isinstance(exclude_id, (list, tuple)):
                exclude_id = exclude_id[0] if exclude_id else None
            exclude_ids = {exclude_id} | self._get_descendants(exclude_id)
            items_to_render = [item for item in self._data if item["id"] not in exclude_ids]

        def walk(parent_id, depth):
            children = sorted([i for i in items_to_render if i.get("parent_id") == parent_id], key=lambda x: (x.get("type", ""), x.get("title", "")))
            for item in children:
                prefix = "· " * depth
                opts.append((f"{prefix}{item['title']}", item["id"]))
                walk(item["id"], depth + 1)
        
        walk(None, 0)
        return opts

    def build_table_rows(self) -> List[Dict[str, Any]]:
        """Tabulator에 표시할 수 있도록 계층 구조를 평탄화하고 텍스트 트리를 만듭니다."""
        rows = []
        
        def _children_map(items):
            cmap = {}
            for it in items:
                cmap.setdefault(it.get("parent_id"), []).append(it)
            def _order_key(item):
                val = item.get("order", "")
                try:
                    return (0, int(val))
                except Exception:
                    return (1, str(val))
            for v in cmap.values():
                v.sort(key=lambda x: (_order_key(x), x.get("title", "")))
            return cmap

        cmap = _children_map(self._data)

        def walk(parent_id, prefix_stack):
            children = cmap.get(parent_id, [])
            total = len(children)
            for idx, child in enumerate(children):
                is_last = idx == total - 1
                branch = "└─ " if is_last else "├─ "
                # widen indent so children sit visibly inside their parent
                indent = "".join(("        " if p else "│       ") for p in prefix_stack)
                if prefix_stack:
                    indent += "        "
                rows.append({
                    "id": child["id"],
                    "title": indent + branch + child["title"],
                    "order": child.get("order", ""),
                    "type": child.get("type"),
                    "status": child.get("status"),
                    "owner": child.get("owner"),
                    "due": child.get("due"),
                })
                walk(child["id"], prefix_stack + [is_last])

        walk(None, [])
        return rows

    def build_flat_options(self) -> Dict[str, str]:
        """'선택/수정 대상' 드롭다운을 위한 계층 구조 옵션을 생성합니다."""
        rows = self.build_table_rows()
        # build_table_rows가 이미 title에 prefix를 적용했으므로 그대로 사용.
        # 반환 타입을 Dict에서 List[tuple]로 변경하여 unhashable 오류 방지
        return {row['title']: row['id'] for row in rows}

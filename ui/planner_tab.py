import datetime

import pandas as pd
import panel as pn

from project_planner import PlannerStore


def _normalize_id(value):
    """Tabulator selections can be nested list/tuple; flatten to first scalar value."""
    while isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value in ("", None):
        return None
    return value


def _parse_date(value):
    """DatePicker expects date/datetime; convert ISO strings safely."""
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except Exception:
        return None


def build_planner_tab(planner_store: PlannerStore):
    selected_ids = []

    def _children_map(items):
        cmap = {}
        for it in items:
            cmap.setdefault(it["parent_id"], []).append(it)
        for v in cmap.values():
            v.sort(key=lambda x: (x["type"], x["title"]))
        return cmap

    def _descendants(item_id, items):
        item_id = _normalize_id(item_id)
        if not item_id:
            return set()
        desc = set()
        changed = True
        while changed:
            changed = False
            for it in items:
                if it["parent_id"] in (desc | {item_id}) and it["id"] not in desc:
                    desc.add(it["id"])
                    changed = True
        return desc

    def build_parent_options(current_id=None):
        current_id = _normalize_id(current_id)
        items = planner_store.list_items()
        blocked = set()
        if current_id:
            blocked |= {current_id}
            blocked |= _descendants(current_id, items)
        opts = [("", None)]
        for it in items:
            if it["id"] in blocked:
                continue
            opts.append((f"{it['title']} ({it['type']})", it["id"]))
        return {label: value for label, value in opts}

    def build_flat_options():
        items = planner_store.list_items()
        cmap = _children_map(items)
        options = []

        def walk(parent_id, depth):
            for item in cmap.get(parent_id, []):
                prefix = "· " * depth
                options.append((f"{prefix}{item['title']} ({item['type']})", item["id"]))
                walk(item["id"], depth + 1)

        walk(None, 0)
        return {label: value for label, value in [("", None)] + options}

    def build_table_rows():
        items = planner_store.list_items()
        cmap = _children_map(items)
        parent_of = {it["id"]: it["parent_id"] for it in items}

        def path_of(item_id):
            parts = []
            cur = item_id
            while cur:
                itm = next((i for i in items if i["id"] == cur), None)
                if not itm:
                    break
                parts.append(itm["title"])
                cur = parent_of.get(cur)
            return "/".join(reversed(parts))

        rows = []

        def walk(parent_id, prefix_stack):
            children = cmap.get(parent_id, [])
            def _order_key(item):
                val = item.get("order", "")
                try:
                    return (0, int(val))
                except Exception:
                    return (1, str(val))
            children = sorted(children, key=lambda x: (_order_key(x), x["title"]))
            total = len(children)
            for idx, child in enumerate(children):
                is_last = idx == total - 1
                branch = "└─ " if is_last else "├─ "
                indent = "".join("│  " for _ in prefix_stack)
                rows.append({
                    "id": child["id"],
                    "title": indent + branch + child["title"],
                    "order": child.get("order", "") or idx + 1,
                    "type": child["type"],
                    "status": child["status"],
                    "owner": child["owner"],
                    "due": child["due"],
                    "path": path_of(child["id"]),
                })
                walk(child["id"], prefix_stack + [is_last])

        walk(None, [])
        return rows

    def build_tabulator(value, config=None):
        for selectable_opt in (True, 'checkbox', 1):
            try:
                kwargs = dict(show_index=False, selectable=selectable_opt, sizing_mode='stretch_both')
                if config:
                    kwargs["configuration"] = config
                return pn.widgets.Tabulator(value, **kwargs)
            except Exception:
                continue
        kwargs = dict(show_index=False, sizing_mode='stretch_both')
        if config:
            kwargs["configuration"] = config
        return pn.widgets.Tabulator(value, **kwargs)

    def build_tree_grid(value, config=None):
        kwargs = dict(
            show_index=False,
            selectable=True,
            sizing_mode='stretch_both',
        )
        if config:
            kwargs["configuration"] = config
        return pn.widgets.Tabulator(value, **kwargs)

    tree_supported = True

    def _strip_path(nodes):
        for n in nodes:
            n.pop("path", None)
            if "_children" in n:
                _strip_path(n["_children"])
    def _annotate_order(nodes):
        if not nodes:
            return
        for idx, n in enumerate(nodes, start=1):
            if not n.get("order"):
                n["order"] = idx
            if "_children" in n:
                _annotate_order(n["_children"])

    planner_columns_tree = [
        {"title": "제목", "field": "title", "formatter": "tree", "editor": False},
        {"title": "정렬", "field": "order", "hozAlign": "center", "width": 70, "editor": False},
        {"title": "구분", "field": "type", "editor": False},
        {"title": "상태", "field": "status", "editor": False},
        {"title": "담당", "field": "owner", "editor": False},
        {"title": "Due Date", "field": "due", "editor": False},
    ]
    planner_columns_plain = [
        {k: v for k, v in col.items() if k != "formatter"}
        for col in planner_columns_tree
    ]

    try:
        tree_rows = planner_store.to_tree_rows()
        _strip_path(tree_rows)
        _annotate_order(tree_rows)
        planner_table = build_tree_grid(
            tree_rows,
            config={
                "layout": "fitColumns",
                "dataTree": True,
                "dataTreeChildField": "_children",
                "dataTreeColumn": "title",
                "dataTreeStartExpanded": True,
                "dataTreeSort": False,
                "index": "id",
                "dataTreeChildIndent": 26,
                "columnDefaults": {"headerSort": False, "editor": False},
            },
        )
    except Exception:
        tree_supported = False
        planner_table = build_tabulator(
            pd.DataFrame(build_table_rows(), columns=["title", "order", "type", "status", "owner", "due", "path", "id"]),
            config={
                "layout": "fitColumns",
                "columnDefaults": {"headerSort": False, "editor": False},
                "columns": planner_columns_plain,
            },
        )

    try:
        planner_table.hidden_columns = ["id", "parent_id", "_children", "path"]
    except Exception:
        pass
    sel_target = pn.widgets.Select(name="선택/수정 대상", options=build_flat_options(), value=None, sizing_mode='stretch_width')
    sel_target_display = pn.widgets.TextInput(name="선택 항목 (표에서 선택)", value="", sizing_mode='stretch_width')
    sel_parent = pn.widgets.Select(
        name="부모 노드",
        options=build_parent_options(),
        value=None,
        sizing_mode='stretch_width'
    )
    inp_title = pn.widgets.TextInput(name="제목", placeholder="예) API Gateway", value="", sizing_mode='stretch_width')
    sel_type = pn.widgets.Select(
        name="구분",
        options={"": None, "Architecture": "Architecture", "Data": "Data", "Feature": "Feature", "UI": "UI", "Schedule": "Schedule"},
        value=None,
        sizing_mode='stretch_width'
    )
    sel_status = pn.widgets.Select(
        name="상태",
        options={"": None, "Planned": "Planned", "In Progress": "In Progress", "Done": "Done", "Hold": "Hold"},
        value=None,
        sizing_mode='stretch_width'
    )
    inp_owner = pn.widgets.TextInput(name="담당", placeholder="예) Infra", value="", sizing_mode='stretch_width')
    inp_due = pn.widgets.DatePicker(name="Due Date", value=None, sizing_mode='stretch_width')
    inp_notes = pn.widgets.TextAreaInput(name="메모", rows=3, value="", sizing_mode='stretch_width')
    inp_notes.css_classes = ["planner-notes"]
    inp_order = pn.widgets.TextInput(name="정렬", placeholder="예) 1", value="", sizing_mode='stretch_width')
    planner_msg = pn.pane.Markdown("", sizing_mode='stretch_width', styles={'font-size': '12px', 'color': '#444'})

    def _label_for_id(item_id):
        item_id = _normalize_id(item_id)
        opts = build_flat_options()
        for label, val in opts.items():
            if val == item_id:
                return label
        return ""

    def refresh_planner(message=""):
        current = [_normalize_id(v) for v in selected_ids]
        if tree_supported:
            planner_table.value = planner_store.to_tree_rows()
        else:
            planner_table.value = pd.DataFrame(build_table_rows(),
                                               columns=["title", "order", "type", "status", "owner", "due", "path", "id"])

        flat_options = build_flat_options()
        sel_target.options = flat_options
        sel_target_display.value = _label_for_id(sel_target.value or (selected_ids[0] if selected_ids else None))

        existing_ids = set(_normalize_id(v) for v in flat_options.values())
        updated_sel = [sid for sid in current if sid in existing_ids]
        selected_ids.clear()
        selected_ids.extend(updated_sel)

        sel_parent.options = build_parent_options(_normalize_id(sel_target.value))
        cur_val = _normalize_id(sel_target.value)
        if cur_val not in existing_ids:
            sel_target.value = selected_ids[0] if selected_ids else None
            sel_target_display.value = _label_for_id(sel_target.value)
        if sel_parent.value and sel_parent.value not in sel_parent.options.values():
            sel_parent.value = None
        if not selected_ids and not sel_target.value:
            try:
                planner_table.selection = []
            except Exception:
                pass
            sel_target_display.value = ""
            sel_parent.value = None
            inp_title.value = ""
            sel_type.value = None
            sel_status.value = None
            inp_owner.value = ""
            inp_due.value = None
            inp_notes.value = ""
            inp_order.value = ""
        planner_msg.object = message

    def load_selection(event=None):
        target_id = _normalize_id(sel_target.value)
        selected_ids.clear()
        if target_id:
            selected_ids.append(target_id)
        item = planner_store.get_item(target_id) if target_id else None
        if not item:
            inp_title.value = ""
            sel_type.value = None
            sel_status.value = None
            inp_owner.value = ""
            inp_due.value = None
            inp_notes.value = ""
            sel_parent.value = None
            return
        inp_title.value = item.get("title", "")
        sel_type.value = item.get("type", "Architecture")
        sel_status.value = item.get("status", "Planned")
        inp_owner.value = item.get("owner", "")
        inp_due.value = _parse_date(item.get("due"))
        inp_notes.value = item.get("notes", "")
        sel_parent.value = item.get("parent_id")
        sel_parent.options = build_parent_options(target_id)
        sel_target_display.value = _label_for_id(target_id)
        inp_order.value = str(item.get("order", "") or "")

    sel_target.param.watch(load_selection, 'value')

    def sync_selection_from_table(event):
        selected_ids.clear()
        if not event.new:
            sel_target.value = None
            sel_target_display.value = ""
            return

        if tree_supported:
            flat_ids = []

            def flatten(nodes):
                for n in nodes:
                    flat_ids.append(n.get("id"))
                    if "_children" in n:
                        flatten(n["_children"])

            flatten(planner_table.value or [])
            for idx in event.new:
                if isinstance(idx, (int, float)) and int(idx) < len(flat_ids):
                    selected_ids.append(flat_ids[int(idx)])
                elif isinstance(idx, str):
                    selected_ids.append(idx)
        else:
            df = planner_table.value if isinstance(planner_table.value, pd.DataFrame) else pd.DataFrame()
            for idx in event.new:
                if isinstance(idx, (int, float)) and idx < len(df):
                    selected_ids.append(df.iloc[int(idx)]["id"])
                elif isinstance(idx, str):
                    selected_ids.append(idx)

        selected_ids[:] = [sid for sid in selected_ids if sid in sel_target.options.values()]
        sel_target.value = selected_ids[0] if selected_ids else None
        sel_target_display.value = _label_for_id(sel_target.value)

    planner_table.param.watch(sync_selection_from_table, 'selection')

    def on_add(event):
        planner_store.add_item(
            parent_id=_normalize_id(sel_parent.value),
            title=inp_title.value,
            item_type=sel_type.value,
            status=sel_status.value,
            owner=inp_owner.value,
            due=str(inp_due.value) if inp_due.value else "",
            notes=inp_notes.value,
            order=inp_order.value,
        )
        refresh_planner("새 항목이 추가되었습니다.")

    def on_update(event):
        target_id = _normalize_id(sel_target.value)
        parent_id = _normalize_id(sel_parent.value)
        if not target_id:
            planner_msg.object = "수정할 항목을 선택하세요."
            return
        items = planner_store.list_items()
        blocked = {target_id} | _descendants(target_id, items)
        if parent_id in blocked:
            planner_msg.object = "자신이나 하위 노드를 부모로 지정할 수 없습니다."
            return
        planner_store.update_item(
            target_id,
            {
                "title": inp_title.value,
                "type": sel_type.value,
                "status": sel_status.value,
                "owner": inp_owner.value,
                "due": str(inp_due.value) if inp_due.value else None,
                "notes": inp_notes.value,
                "order": inp_order.value,
                "parent_id": parent_id,
            }
        )
        refresh_planner("항목이 수정되었습니다.")

    def on_delete(event):
        targets_to_delete = selected_ids if selected_ids else [sel_target.value]
        targets = [_normalize_id(t) for t in targets_to_delete if _normalize_id(t)]

        if not targets:
            planner_msg.object = "삭제할 항목을 선택하세요."
            return
        for tid in targets:
            planner_store.delete_item(tid)

        refresh_planner(f"{len(targets)}건 삭제 완료.")

    btn_add = pn.widgets.Button(name="추가", button_type="success", width=60, height=26)
    btn_update = pn.widgets.Button(name="저장", button_type="primary", width=60, height=26)
    btn_delete = pn.widgets.Button(name="삭제", button_type="danger", width=60, height=26)
    btn_reload = pn.widgets.Button(name="리로드", button_type="default", width=70, height=26)

    btn_add.on_click(on_add)
    btn_update.on_click(on_update)
    btn_delete.on_click(on_delete)
    btn_reload.on_click(lambda e: refresh_planner("새로고침했습니다."))

    planner_left = pn.Column(
        pn.pane.Markdown("**Tree**", margin=(0, 0, 6, 0)),
        pn.Column(
            planner_table,
            sizing_mode='stretch_both',
        ),
        sizing_mode='stretch_both',
        css_classes=['planner-left'],
    )

    for w in (sel_target_display, sel_parent, inp_title, sel_type, sel_status, inp_owner, inp_due):
        existing_styles = w.styles or {}
        existing_styles.update({"font-size": "11px", "color": "#212121"})
        w.width = None
        w.sizing_mode = 'stretch_width'
        w.styles = existing_styles
    inp_notes.width = None
    inp_notes.sizing_mode = 'stretch_width'
    inp_notes.rows = 10
    inp_notes.height = 250
    inp_notes.styles = {"font-size": "11px", "color": "#212121", "min-height": "250px", "resize": "vertical"}

    btn_add.height = btn_update.height = btn_delete.height = btn_reload.height = 24
    for idx, b in enumerate((btn_add, btn_update, btn_delete, btn_reload)):
        b.styles = {"font-weight": "500", "font-size": "9px", "padding": "0px 8px", "line-height": "9px"}
        b.margin = (0, 8 if idx < 3 else 0, 0, 0)
    btn_reload.button_type = "warning"

    def field_col(label, widget):
        widget.name = ""
        label_pane = pn.pane.Markdown(
            f"**{label}**",
            width=80,
            align='center',
            styles={'font-size': '12px', 'color': '#333', 'text-align': 'right', 'margin-right': '10px'}
        )
        return pn.Row(
            label_pane,
            widget,
            sizing_mode='stretch_width', align='center', margin=(0, 10, 8, 10)
        )

    btn_row = pn.Row(
        pn.Spacer(),
        btn_add, btn_update, btn_delete, btn_reload,
        pn.Spacer(),
        sizing_mode='stretch_width',
        align='center',
        margin=(12, 10, 4, 10),
    )

    planner_right = pn.Column(
        field_col("선택/수정 대상", sel_target_display),
        field_col("부모 노드", sel_parent),
        field_col("제목", inp_title),
        field_col("구분", sel_type),
        field_col("상태", sel_status),
        field_col("담당", inp_owner),
        field_col("Due Date", inp_due),
        field_col("정렬", inp_order),
        field_col("메모", inp_notes),
        btn_row,
        planner_msg,
        sizing_mode='stretch_both',
        css_classes=['planner-right'],
        styles={'margin-left': '12px'},
    )
    planner_panel = pn.Column(
        pn.Row(
            planner_left,
            planner_right,
            sizing_mode='stretch_both',
            styles={'height': '100%'},
            css_classes=['planner-split'],
        ),
        sizing_mode='stretch_both',
        styles={'padding': '6px', 'height': '100%'}
    )

    refresh_planner("Planner를 로드했습니다.")
    return planner_panel


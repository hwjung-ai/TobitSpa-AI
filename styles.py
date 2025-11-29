CHAT_CSS = """
:root { --type-ramp-base-font-size: 11px !important; }
body, .bk, .bk-root, table {
    font-family: 'Malgun Gothic','Segoe UI',sans-serif !important;
    font-size: 11px !important;
}
.bk-btn, .bk-input, select {
    font-size: 11px !important;
    height: 26px !important;
    min-height: 26px !important;
    padding: 0 6px !important;
}
.bk-tab {
    font-size: 11px !important;
    padding: 3px 8px !important;
    height: 26px !important;
}
.user-msg-box {
    float: right; clear: both;
    background-color: #f3f4f6; color: #222;
    border-radius: 18px;
    padding: 10px 14px; margin: 6px 12px 6px 40px;
    width: fit-content; max-width: 80%; text-align: left; font-size: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.bot-msg-box {
    float: left; clear: both;
    background-color: #ffffff; color: #222;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 10px 14px; margin: 6px 40px 6px 12px;
    width: fit-content; max-width: 90%; font-size: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
"""

PLANNER_CSS = """
.planner-split {
    display: flex;
    align-items: stretch;
    width: 100%;
    height: 100%;
    min-height: 480px;
}
.planner-split,
.planner-split .bk,
.planner-split .bk * {
    font-family: 'Malgun Gothic','Segoe UI',sans-serif !important;
    font-size: 11px !important;
}
.planner-split > .bk-Column.planner-left {
    flex: 1 1 0% !important;
    min-width: 340px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    height: 100%;
    font-family: 'Malgun Gothic','Segoe UI',sans-serif;
    font-size: 11px;
}
.planner-split > .bk-Column.planner-right {
    flex: 1 1 0% !important;
    min-width: 280px;
    max-width: none;
    overflow: auto;
    height: 100%;
    font-family: 'Malgun Gothic','Segoe UI',sans-serif;
    font-size: 11px;
    background-color: white;
    color: black;
    padding: 10px;
}
.planner-split .bk-Tabulator,
.planner-split .bk-Tabulator .tabulator,
.planner-split .bk-Tabulator .tabulator-cell,
.planner-split .bk-Tabulator .tabulator-col,
.planner-split .bk-Tabulator .tabulator-header,
.planner-split .tabulator .tabulator-row .tabulator-cell {
    font-family: 'Malgun Gothic','Segoe UI',sans-serif;
    font-size: 11px;
}

.planner-split .planner-left .bk-Tabulator {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    overflow: hidden;
}
.planner-split .planner-left .bk-Tabulator .tabulator-tableholder {
    overflow: auto !important;
    height: 100% !important;
    max-height: 100% !important;
    min-height: 0;
}
.planner-split .planner-left .bk-Tabulator .tabulator-tableholder::-webkit-scrollbar {
    width: 10px;
    height: 10px;
    background: #f2f3f5;
}
.planner-split .planner-left .bk-Tabulator .tabulator-tableholder::-webkit-scrollbar-thumb {
    background: #a5b4c4;
    border-radius: 6px;
    border: 2px solid #f2f3f5;
}
.planner-split .planner-left .bk-Tabulator .tabulator-tableholder::-webkit-scrollbar-thumb:hover {
    background: #7f91a6;
}
.planner-split .planner-left .bk-Tabulator .tabulator-tableholder {
    scrollbar-width: thin;
    scrollbar-color: #a5b4c4 #f2f3f5;
}

.planner-split .planner-left .tabulator .tabulator-cell[tabulator-field="title"] {
    white-space: pre;
    font-family: 'Consolas','Courier New',monospace;
}

/* Planner notes textarea: override global input height */
.planner-notes textarea,
.planner-notes .bk-input {
    height: auto !important;
    min-height: 200px !important;
    resize: vertical;
    width: 100%;
    line-height: 1.4;
    padding: 6px 8px;
}
"""


CHAT_CSS = """
:root { --type-ramp-base-font-size: 11px !important; --app-header-height: 44px; }

body, .bk, .bk-root, table {
    font-family: 'Malgun Gothic','Segoe UI',sans-serif !important;
    font-size: 11px !important;
}

html, body {
    height: 100%;
    margin: 0 !important;
    overflow: hidden !important; /* prevent outer page scroll */
}
.bk-root {
    height: 100vh !important;
    overflow: hidden !important;
}
.bk.bk-Column, .bk-Column {
    min-height: 0 !important;
}
.bk-main, .bk-main > .bk-Column {
    height: calc(100vh - var(--app-header-height)) !important; /* fill viewport minus fixed header */
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}
.bk-main .bk-Tabs {
    height: 100% !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}
.bk-main .bk-Tabs .bk-Column,
.bk-main .bk-Tabs .bk-Row,
.bk-main .bk-Tabs .bk-tab-panel {
    height: 100% !important;
    min-height: 0 !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}
.bk-main .bk-Tabs .bk-tab-panel > .bk-Column {
    flex: 1 1 auto !important;
    min-height: 0 !important;
}
.bk-main .bk-Tabs .bk-tab-panel .bk-Column {
    flex: 1 1 auto !important;
}

/* Base control sizing */
.bk-btn, .bk-input, select {
    font-size: 11px !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 6px !important;
}
.bk-tab {
    font-size: 11px !important;
    padding: 3px 8px !important;
    height: 26px !important;
}

/* Chat bubbles: allow multi-line answers, use most of available width */
.user-msg-box {
    display: inline-block;
    vertical-align: top;
    clear: both;
    background-color: #f3f4f6;
    color: #222;
    border-radius: 18px;
    padding: 10px 14px;
    margin: 6px 12px 6px 40px;
    max-width: calc(100% - 60px);
    text-align: left;
    font-size: 13px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}

.bot-msg-box {
    display: inline-block;
    vertical-align: top;
    clear: both;
    background-color: #ffffff;
    color: #222;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 10px 14px;
    margin: 6px 40px 6px 12px;
    max-width: calc(100% - 60px);
    font-size: 13px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}

/* Make sure each message row clears floats so container height expands */
.bot-msg-box + div.clearfix,
.user-msg-box + div.clearfix {
    display: block;
    clear: both;
    height: 0;
    line-height: 0;
}

/* Chat layout: ensure input stays visible and log scrolls
   We rely on the template to set the main height. Use scrollable log and fixed input row. */
.chat-box {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
}

/* Chat log container should take available vertical space and scroll internally */
.chat-log-container {
    flex: 1 1 auto;
    overflow-y: auto !important;
    padding: 10px;
    min-height: 0 !important;
}

/* Input row: align items vertically and keep buttons aligned with input */
.chat-input-row {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 8px 8px;
    background: #fff;
    border-top: 1px solid #e5e7eb;
    position: sticky;
    bottom: 0;
    z-index: 10;
}

/* Ensure the panel input expands and buttons keep consistent height */
.chat-input-row .bk-input {
    flex: 1 1 auto;
    min-width: 0;
    height: 36px !important;
}
.chat-input-row .bk-input input {
    height: 36px !important;
    line-height: 36px !important;
    padding: 0 10px !important;
    box-sizing: border-box;
}
.chat-input-row .bk-btn {
    height: 36px !important;
    padding: 0 10px !important;
}

/* Make test/send buttons visually aligned */
.chat-send-btn button,
.chat-test-btn button {
    height: 36px !important;
    line-height: 34px !important;
}

/* History item layout: title fills space up to the 'x' button */
.history-item {
    display: flex;
    align-items: center;
    gap: 6px;
}
.history-item button:first-child {
    flex: 1 1 auto;
    min-width: 0;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.history-item button:last-child {
    flex: 0 0 auto;
    width: 18px;
    min-width: 18px;
    padding: 0 !important;
}

/* Ensure long inputs behave sensibly */
input.bk-input, .bk-input input[type="text"], .bk-input input {
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    overflow: hidden !important;
}

/* Narrow-width tweaks */
@media (max-width: 900px) {
    .user-msg-box,
    .bot-msg-box {
        max-width: 95% !important;
        margin-left: 8px !important;
        margin-right: 8px !important;
    }
    .chat-input-row {
        padding: 6px 4px !important;
    }
}

/* Compact Material header (top app bar) */
.mdc-top-app-bar,
.mdc-top-app-bar__row {
    height: 44px !important;
    min-height: 44px !important;
}
.mdc-top-app-bar__title {
    font-size: 12px !important;
    line-height: 44px !important;
}
.bk-header, .bk-Header {
    margin-bottom: 0 !important;
}
"""

PLANNER_CSS = """
:root {
    --planner-grid-font: 12px;
    --planner-grid-line: 1.2;
    --planner-grid-pad-v: 3px;
    --planner-grid-pad-h: 5px;
}
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
    flex: 0 0 40% !important;
    width: 40% !important;
    max-width: 42% !important;
    min-width: 320px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    height: 100%;
    font-family: 'Malgun Gothic','Segoe UI',sans-serif;
}
.planner-split > .bk-Column.planner-right {
    flex: 0 0 60% !important;
    width: 60% !important;
    max-width: 60% !important;
    min-width: 360px;
    overflow: auto;
    height: 100%;
    font-family: 'Malgun Gothic','Segoe UI',sans-serif;
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
    font-size: var(--planner-grid-font, 12px) !important;
    line-height: var(--planner-grid-line, 1) !important;
}
.planner-split .tabulator .tabulator-row .tabulator-cell,
.planner-split .tabulator .tabulator-header .tabulator-col .tabulator-col-content {
    padding: var(--planner-grid-pad-v, 3px) var(--planner-grid-pad-h, 5px) !important;
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

/* Compact controls inside Planner: align with global base sizing (11px/28px) */
.planner-split .bk-input,
.planner-split select,
.planner-split .bk-btn {
    font-size: 12px !important;
    height: 26px !important;
    min-height: 26px !important;
    padding: 0 6px !important;
}
.planner-split .bk-input input {
    height: 26px !important;
    line-height: 26px !important;
    padding: 0 6px !important;
}
.planner-split .bk-btn button {
    height: 26px !important;
    line-height: 24px !important;
}
"""

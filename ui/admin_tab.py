import os

import panel as pn

from utils import get_file_list_recursive, load_file, save_file


def build_admin_editor():
    # 파일 선택: 이동 버튼 없는 리스트(경로 기반)로 제공
    files = get_file_list_recursive()
    file_list = pn.widgets.MultiSelect(
        name="Files",
        options=files,
        size=18,
        height=300,
        width=300
    )
    btn_save = pn.widgets.Button(name='Save', button_type='primary',
                                 width=60, height=26)
    editor = pn.widgets.CodeEditor(
        value=load_file(files[0]) if files and files[0] not in ("No Files", "Error") else "",
        language='python',
        theme='monokai',
        sizing_mode='stretch_both',
        styles={'font-size': '11px'}
    )
    # 기본 선택을 첫 번째 파일로 세팅
    if files and files[0] not in ("No Files", "Error"):
        file_list.value = [files[0]]

    def _current_path(vals):
        if isinstance(vals, (list, tuple)) and vals:
            return vals[-1]
        return None

    def on_select(e):
        path = _current_path(e.new)
        if path:
            editor.value = load_file(path)

    file_list.param.watch(on_select, 'value')
    btn_save.on_click(lambda e: save_file(_current_path(file_list.value), editor.value) if _current_path(file_list.value) else None)
    editor_box = pn.Row(
        pn.Column(file_list, sizing_mode='stretch_height', width=320),
        pn.Column(pn.Row(btn_save, align='start'), editor, sizing_mode='stretch_both'),
        sizing_mode='stretch_both',
        styles={'height': '100%'}
    )
    return editor_box

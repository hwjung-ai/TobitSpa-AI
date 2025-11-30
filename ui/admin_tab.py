import panel as pn

from utils import get_real_file_list, load_file, save_file


def build_admin_editor():
    files = get_real_file_list()
    init_file = files[0] if files else "No Files"
    sel_file = pn.widgets.Select(options=files, value=init_file,
                                 width=150, height=26)
    btn_save = pn.widgets.Button(name='Save', button_type='primary',
                                 width=60, height=26)
    editor = pn.widgets.CodeEditor(
        value=load_file(init_file),
        language='python',
        theme='monokai',
        sizing_mode='stretch_both',
        styles={'font-size': '11px'}
    )

    def on_file_change(e):
        editor.value = load_file(e.new)

    sel_file.param.watch(on_file_change, 'value')
    btn_save.on_click(lambda e: save_file(sel_file.value, editor.value))
    editor_box = pn.Column(
        pn.Row(sel_file, btn_save, align='center'),
        editor,
        sizing_mode='stretch_both',
        styles={'height': '100%'}
    )
    return editor_box


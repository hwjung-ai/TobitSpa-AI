import panel as pn

from api import upload_via_python


def build_upload_tab():
    upload_file = pn.widgets.FileInput(
        accept='.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx',
        multiple=True,
        sizing_mode='stretch_width'
    )
    meta_title = pn.widgets.TextInput(name="제목*", width=200)
    meta_system = pn.widgets.TextInput(name="시스템*", width=160)
    meta_category = pn.widgets.TextInput(name="카테고리*", width=160)
    meta_owner = pn.widgets.TextInput(name="담당*", width=140)
    meta_tags = pn.widgets.TextInput(name="태그(쉼표)", width=220)
    btn_upload = pn.widgets.Button(name="업로드", button_type="primary", width=80)
    upload_status = pn.pane.Markdown("", sizing_mode='stretch_width')

    def _build_files_payload():
        names = upload_file.filename
        mime = upload_file.mime_type
        data = upload_file.value
        if not data:
            return []
        if isinstance(data, list):
            files = []
            for idx, raw in enumerate(data):
                fname = names[idx] if isinstance(names, list) else f"file_{idx}"
                mtype = mime[idx] if isinstance(mime, list) else "application/octet-stream"
                files.append((fname, raw, mtype))
            return files
        return [(names or "file.bin", data, mime or "application/octet-stream")]

    def do_upload(event=None):
        req_fields = [meta_title.value, meta_system.value, meta_category.value, meta_owner.value]
        if not all(req_fields):
            upload_status.object = "필수 항목(제목/시스템/카테고리/담당)을 입력하세요."
            return
        files = _build_files_payload()
        if not files:
            upload_status.object = "파일을 선택하세요."
            return
        try:
            result = upload_via_python(
                files,
                meta_title.value,
                meta_system.value,
                meta_category.value,
                meta_owner.value,
                meta_tags.value,
            )
            upload_status.object = f"업로드 완료: {result}"
        except Exception as e:
            upload_status.object = f"업로드 실패: {e}"

    btn_upload.on_click(do_upload)

    upload_tab = pn.Column(
        pn.Row(meta_title, meta_system, meta_category, meta_owner, meta_tags, sizing_mode='stretch_width'),
        upload_file,
        pn.Row(btn_upload, sizing_mode='stretch_width'),
        upload_status,
        sizing_mode='stretch_both',
        styles={'padding': '8px'}
    )
    return upload_tab


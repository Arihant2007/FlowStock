import re

with open('tests/test_bom_e2e.py', 'r') as f:
    content = f.read()

# Replace preview 1
p1_find = 'preview = svc.preview_bom_upload(file_bytes, "bom.xlsx")'
p1_repl = 'preview = svc.preview_bom_upload(file_bytes, "bom.xlsx", session_id=None, current_user_id=1)'
content = content.replace(p1_find, p1_repl)

# Replace commit 1
c1_find = 'svc.commit_bom_upload(file_bytes, "bom.xlsx", created_by=1)'
c1_repl = 'svc.commit_bom_upload(session_id=preview.session_id, current_user_id=1)'
content = content.replace(c1_find, c1_repl)

# Replace commit 2
c2_find = 'svc.commit_bom_upload(valid_file_bytes, "bom_valid.xlsx", created_by=1)'
c2_repl = '''valid_preview = svc.preview_bom_upload(valid_file_bytes, "bom_valid.xlsx", session_id=None, current_user_id=1)
    svc.commit_bom_upload(session_id=valid_preview.session_id, current_user_id=1)'''
content = content.replace(c2_find, c2_repl)

with open('tests/test_bom_e2e.py', 'w') as f:
    f.write(content)

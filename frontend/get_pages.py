import os, re

frontend_pages_dir = r'c:\Users\Arihant\OneDrive\Apps\Desktop\Placement\ITC-2\frontend\src\pages'
print("--- FRONTEND PAGES ---")
for root, dirs, files in os.walk(frontend_pages_dir):
    for file in files:
        if file.endswith('.tsx'):
            rel_path = os.path.relpath(os.path.join(root, file), frontend_pages_dir)
            print(f'- {rel_path}')

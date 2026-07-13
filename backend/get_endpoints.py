import os
import re

backend_dir = r'c:\Users\Arihant\OneDrive\Apps\Desktop\Placement\ITC-2\backend\app\domains'
print("--- BACKEND ENDPOINTS ---")
for root, _, files in os.walk(backend_dir):
    for file in files:
        if file == 'router.py':
            path = os.path.join(root, file)
            with open(path, encoding='utf-8') as f:
                content = f.read()
                endpoints = re.findall(r'@router\.(get|post|put|delete|patch)\([\'\"]([^\'\"]+)[\'\"]', content)
                if endpoints:
                    print(f'\n--- {os.path.basename(root)}/router.py ---')
                    for method, endpoint in endpoints:
                        print(f'{method.upper()} {endpoint}')

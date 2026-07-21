import pandas as pd
import os

os.chdir(r"c:\Users\Arihant\OneDrive\Apps\Desktop\Placement\ITC-2\backend")

# 1. Material Master Template
df_materials = pd.DataFrame({
    'Material Code': ['TEST-MAT-1', 'TEST-MAT-2'],
    'Material Name': ['Test Material 1', 'Test Material 2'],
    'UOM': ['KG', 'EA'],
    'Category': ['RM', 'PM'],
    'Material Type': ['Raw Material', 'Packaging Material'],
    'Group': ['Group A', 'Group B']
})
df_materials.to_excel("Material_Master_Template.xlsx", index=False)

# 2. Inventory Template
# Let's check what headers the inventory upload expects. 
# Usually: ['Material Code', 'Quantity', 'Warehouse'] or something similar.

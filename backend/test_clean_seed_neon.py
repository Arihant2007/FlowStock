import os
from dotenv import load_dotenv

load_dotenv()

conn_str = os.getenv("DATABASE_URL")
if conn_str.startswith("postgresql://"):
    parts = conn_str.split('?')
    base_url = parts[0]
    base_parts = base_url.rsplit('/', 1)
    new_base_url = base_parts[0] + "/audit_test_db"
    new_conn_str = new_base_url
    if len(parts) > 1:
        new_conn_str += "?" + parts[1]
    
    os.environ["DATABASE_URL"] = new_conn_str

print(f"Running seed script against: {os.environ['DATABASE_URL']}")

# Run the actual seed script using exec
with open("seed.py", "r", encoding="utf-8") as f:
    code = f.read()
    exec(code)

import re

with open('app/domains/master/service.py', 'r') as f:
    content = f.read()

find = "if session.expires_at < datetime.now(timezone.utc):"
repl = "if (session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at) < datetime.now(timezone.utc):"
content = content.replace(find, repl)

with open('app/domains/master/service.py', 'w') as f:
    f.write(content)

import re

with open('app/domains/master/service.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 548 <= i <= 631:
        if line.strip():
            new_lines.append('    ' + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('app/domains/master/service.py', 'w') as f:
    f.writelines(new_lines)

import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Replace imports
    content = re.sub(r'from datetime import UTC, datetime\b', r'from datetime import datetime, timezone', content)
    content = re.sub(r'from datetime import datetime, timedelta, UTC\b', r'from datetime import datetime, timedelta, timezone', content)
    content = re.sub(r'from datetime import UTC, datetime, timedelta\b', r'from datetime import datetime, timezone, timedelta', content)
    content = re.sub(r'from datetime import datetime, UTC\b', r'from datetime import datetime, timezone', content)

    # Replace usages
    content = re.sub(r'\bdatetime\.now\(UTC\)', r'datetime.now(timezone.utc)', content)
    content = re.sub(r'tzinfo=UTC\b', r'tzinfo=timezone.utc', content)
    content = re.sub(r'\bastimezone\(UTC\)', r'astimezone(timezone.utc)', content)

    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")

root_dir = r"C:\Users\Ashok\Desktop\CELTM WEB\backend\app"
for d, _, fs in os.walk(root_dir):
    for f in fs:
        if f.endswith('.py'):
            fix_file(os.path.join(d, f))


from datetime import datetime
import re

def parse_date(date_str):
    if not date_str:
        return None
    try:
        match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)
        if match:
            clean_date = match.group(1).replace('.', '-')
            return datetime.strptime(clean_date, '%Y-%m-%d')
        return None
    except:
        return None

# Test Case
raw_date = "등록일2025.12.24" # This is exactly what we saw in debug output (sr-only text is included in .text?)
# Wait, BeautifulSoup .get_text() likely includes hidden text.
# The debug output showed: Selector 'span.date' result: <span class="date"><span class="sr-only">등록일</span>2025.12.24</span>

# If we run .get_text(strip=True) on that HTML:
# It becomes "등록일2025.12.24"
parsed = parse_date(raw_date)
print(f"Input: {raw_date} -> Parsed: {parsed}")

raw_date_2 = "2025.12.22"
print(f"Input: {raw_date_2} -> Parsed: {parse_date(raw_date_2)}")

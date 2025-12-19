import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

supabase = create_client(url, key)

# Try inserting a dummy record
test_data = {
    "agency": "FSC",
    "title": "Test Article - DB 연결 테스트",
    "link": "https://test.example.com/article/test123",
    "published_at": datetime.now().isoformat(),
    "content": "This is a test content for debugging purposes.",
    "analysis_result": {
        "summary": ["Test summary point 1"],
        "impact_analysis": "Test impact",
        "risk_level": "Low",
        "keywords": ["test"]
    }
}

try:
    result = supabase.table("articles").insert(test_data).execute()
    print(f"Insert SUCCESS: {result.data}")
except Exception as e:
    import traceback
    print(f"Insert FAILED:")
    traceback.print_exc()

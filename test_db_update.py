import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

# Get first article
response = supabase.table("articles").select("id, title, analysis_result").limit(1).execute()
if not response.data:
    print("No articles found.")
    exit()

article = response.data[0]
print(f"Testing update on: {article['title']}")
print(f"Before: {article.get('analysis_result')}")

# Dummy result
dummy_result = {
    "summary": ["Test update"],
    "keywords": ["test"],
    "risk_level": "Low", 
    "impact_analysis": "None",
    "is_relevant": True
}

try:
    res = supabase.table("articles").update({"analysis_result": dummy_result}).eq("id", article['id']).execute()
    print("Update successful.")
    print(f"After: {res.data[0].get('analysis_result')}")
except Exception as e:
    print(f"Update Failed: {e}")

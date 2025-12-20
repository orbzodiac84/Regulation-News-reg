from src.db.client import supabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CheckLatest")

def check_latest_articles():
    # Fetch top 5 latest articles by published_at
    res = supabase.table('articles').select('*').order('published_at', desc=True).limit(5).execute()
    
    print(f"Total articles found: {len(res.data)}")
    for item in res.data:
        print(f"Title: {item['title'][:30]}...")
        print(f"Agency: {item['agency']}")
        print(f"Published At: {item['published_at']}")
        print(f"Created At:   {item['created_at']}")
        print("-" * 30)

if __name__ == "__main__":
    check_latest_articles()

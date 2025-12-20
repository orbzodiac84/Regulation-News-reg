from src.collectors.scraper import ContentScraper
from datetime import datetime
import json
import logging
import os

logging.basicConfig(level=logging.INFO)

def test_bok_scraping():
    scraper = ContentScraper()
    
    # Load config manually to ensure we use current agencies.json
    with open('config/agencies.json', 'r', encoding='utf-8') as f:
        agencies = json.load(f)['agencies']
        
    bok_config = next(a for a in agencies if a['code'] == 'BOK')
    
    # Fetch list items
    items = scraper.fetch_list_items(bok_config)
    
    print(f"Fetched {len(items)} items from BOK")
    for item in items[:5]:
        print(f"Title: {item['title']}")
        print(f"Published At: {item['published_at']}")
        print("-" * 30)

if __name__ == "__main__":
    test_bok_scraping()

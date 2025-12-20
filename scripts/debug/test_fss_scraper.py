from src.collectors.scraper import ContentScraper
import json
import logging

logging.basicConfig(level=logging.INFO)

def test_fss_scraping():
    scraper = ContentScraper()
    with open('config/agencies.json', 'r', encoding='utf-8') as f:
        agencies = json.load(f)['agencies']
    fss_config = next(a for a in agencies if a['code'] == 'FSS')
    
    items = scraper.fetch_list_items(fss_config)
    print(f"Fetched {len(items)} items from FSS")
    for item in items[:3]:
        print(f"Title: {item['title']}")
        print(f"Published At: {item['published_at']}")
        print("-" * 30)

if __name__ == "__main__":
    test_fss_scraping()

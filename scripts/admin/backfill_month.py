from datetime import datetime, timedelta
from src.collectors.scraper import ContentScraper
from src.pipeline import Pipeline
from src.db.client import supabase
import json
import logging
import time

# Setup logger specially for backfill
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backfill")

def run_backfill():
    logger.info("Starting 1-Month Backfill Process...")
    
    # 1. Initialize Components
    # We use Pipeline to reuse processing logic (Filter -> Analyze -> DB)
    # But we need to override the collector's 'cutoff_date' manually.
    pipeline = Pipeline("config/agencies.json")
    scraper = ContentScraper()
    
    # Target date: 30 days ago
    target_date = datetime.now() - timedelta(days=30)
    logger.info(f"Target Cutoff Date: {target_date.strftime('%Y-%m-%d')}")

    # 2. Iterate Agencies (Only Scrapers usually need deep backfill, RSS is limited by feed)
    # But we will try to handle scrapers specifically here.
    with open("config/agencies.json", 'r', encoding='utf-8') as f:
        agencies = json.load(f)['agencies']

    # Ad-hoc configurations for Backfill (Scraping mode)
    # Mapping Agency Code -> List of Sources
    adhoc_sources = {
        'FSC': [
            {
                'name': 'FSC Press',
                'url': "https://www.fsc.go.kr/no010101",
                'selector': {'list': "#board_list tbody tr", 'title': ".subject a", 'date': "td:nth-of-type(4)", 'link': ".subject a"},
                'page_param': 'curPage={page}' # FSC uses curPage
            },
            {
                'name': 'FSC Briefing',
                'url': "https://www.fsc.go.kr/no010102",
                'selector': {'list': "#board_list tbody tr", 'title': ".subject a", 'date': "td:nth-of-type(4)", 'link': ".subject a"},
                'page_param': 'curPage={page}'
            }
        ],
        'MOEF': [
            {
                'name': 'MOEF Press',
                'url': "https://www.moef.go.kr/nw/nes/nesdta.do",
                'base_params': "bbsId=MOSFBBS_000000000028&menuNo=4010100", 
                'selector': {'list': "table.board-list tbody tr", 'title': "td.title a", 'date': "td:nth-of-type(4)", 'link': "td.title a"},
                'page_param': '&pageIndex={page}' # Appended to base_params
            },
            {
                'name': 'MOEF Explain',
                'url': "https://www.moef.go.kr/nw/nes/nesdta.do",
                'base_params': "bbsId=MOSFBBS_000000000029&menuNo=4010200",
                'selector': {'list': "table.board-list tbody tr", 'title': "td.title a", 'date': "td:nth-of-type(4)", 'link': "td.title a"},
                'page_param': '&pageIndex={page}'
            }
        ]
    }

    # Iterate ALL Agencies in Config
    with open("config/agencies.json", 'r', encoding='utf-8') as f:
        agencies = json.load(f)['agencies']

    for agency in agencies:
        code = agency['code']
        
        # 1. Decide which sources to scrape for this agency
        # If it's in our ad-hoc list, use those (FSC, MOEF)
        # If it's a scraper by default (BOK, FSS), use the agency config itself.
        
        targets = []
        if code in adhoc_sources:
            targets = adhoc_sources[code]
        elif agency['collection_method'] == 'scraper':
            targets = [{
                'name': f"{code} Standard",
                'url': agency['url'],
                'selector': agency.get('selector'),
                'page_param': None # Will try auto-detect
            }]
        else:
            logger.info(f"Skipping {code}: No backfill strategy for RSS-only without ad-hoc override.")
            continue

        for target in targets:
            logger.info(f"Backfilling {code} - {target['name']}...")
            
            base_url = target['url']
            
            for page in range(1, 25): # Increased to 25 pages to cover 1 month safely
                # Construct URL
                if code == 'MOEF':
                    # MOEF needs base_params + page
                    full_params = f"{target['base_params']}{target['page_param'].format(page=page)}"
                    paged_url = f"{base_url}?{full_params}"
                elif 'page_param' in target and target['page_param']:
                     # FSC
                    separator = "&" if "?" in base_url else "?"
                    paged_url = f"{base_url}{separator}{target['page_param'].format(page=page)}"
                else:
                    # BOK / FSS (Auto-detect from previous logic)
                    if "pageIndex=" in base_url:
                        paged_url = base_url.replace("pageIndex=1", f"pageIndex={page}")
                    elif "list.do" in base_url:
                        separator = "&" if "?" in base_url else "?"
                        paged_url = f"{base_url}{separator}pageIndex={page}"
                    else:
                        paged_url = base_url # Fallback

                # Prepare Temp Config
                agency_copy = agency.copy()
                agency_copy['url'] = paged_url
                if 'selector' in target:
                     agency_copy['selector'] = target['selector']
                
                logger.info(f"  > Page {page} (URL: ...{paged_url[-40:]})")

                # Fetch
                items = scraper.fetch_list_items(agency_copy, last_crawled_date=target_date)
                
                if not items:
                    logger.info("  > No items found. Stopping source.")
                    break
                
                items.sort(key=lambda x: x['published_at'])
                if not items: break
                
                oldest_item_date = datetime.fromisoformat(items[0]['published_at']).replace(tzinfo=None)
                logger.info(f"    Found {len(items)} items. Oldest: {oldest_item_date.date()}")
                
                processed_count = 0
                for item in items:
                    # Deduplication (Title check loosely for safety)
                    exists = supabase.table('articles').select('id').eq('title', item['title']).execute()
                    if exists.data:
                        continue
                    
                    pipeline._process_single_item(item)
                    processed_count += 1
                
                logger.info(f"    Processed {processed_count} new items.")
                
                if oldest_item_date < target_date:
                    logger.info("    Target date reached. Next source.")
                    break
                
                time.sleep(1.5)

    logger.info("Backfill complete.")

if __name__ == "__main__":
    run_backfill()

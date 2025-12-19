import os
import json
import logging
from datetime import datetime
from src.collectors.rss_parser import collect_all_rss
from src.collectors.scraper import ContentScraper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'agencies.json')

def load_agency_map():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return {agency['id']: agency for agency in data['agencies']}

def run_cycle():
    """
    Executes one full cycle of collection -> analysis -> comparison.
    """
    try:
        logger.info("Starting MarketPulse-Reg Cycle...")

        # Initialize Services
        try:
            from src.services.analyzer import HybridAnalyzer
            analyzer = HybridAnalyzer()
        except Exception as e:
            logger.error(f"Failed to init Analyzer: {e}")
            analyzer = None

        try:
            from src.services.notifier import TelegramNotifier
            notifier = TelegramNotifier()
        except Exception:
            notifier = None

        try:
            from src.db.client import supabase
        except Exception:
            supabase = None
            logger.error("Supabase client not available.")

        # Load Agency Config (using code as key now)
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # Map using 'code' as ID, fallback 'id'
                agency_map = { a.get('code') or a.get('id'): a for a in config_data['agencies'] }
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return

        scraper = ContentScraper()
        all_items = []

        # --- Phase 1: Collect Items (Hybrid) ---
        
        # 1. RSS Collection
        # collect_all_rss() already iterates agencies.json.
        # We need to make sure rss_parser uses the same file or we pass configs.
        # rss_parser loads file independently. Ensuring it supports 'code' and 'collection_method' check (DONE in Step 1865).
        
        rss_items = collect_all_rss()
        logger.info(f"Collected {len(rss_items)} items from RSS targets.")
        all_items.extend(rss_items)

        # 2. Scraper Collection
        # Identify scraper targets from loaded map
        scraper_targets = [a for a in agency_map.values() if a.get('collection_method') == 'scraper']
        
        for agency in scraper_targets:
            agency_id = agency.get('code') or agency.get('id')
            logger.info(f"Starting HTML scraping for {agency_id}...")
            
            # Determine Last Crawled Date (for Incremental)
            last_date = None
            if supabase:
                try:
                    res = supabase.table('articles').select('published_at').eq('agency', agency_id).order('published_at', desc=True).limit(1).execute()
                    if res.data and len(res.data) > 0:
                        last_raw = res.data[0]['published_at']
                        try:
                            from dateutil import parser
                            last_date = parser.parse(last_raw)
                        except:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to fetch last crawled date for {agency_id}: {e}")

            # Fetch items
            scraped_items = scraper.fetch_list_items(agency, last_crawled_date=last_date)
            logger.info(f"  > Scraped {len(scraped_items)} new items from {agency_id}.")
            all_items.extend(scraped_items)

        if not all_items:
            logger.warning("No new items found from any source.")
            return

        # --- Phase 2: Process & Analyze ---
        
        logger.info(f"Total items to process: {len(all_items)}")

        for item in all_items: 
            agency_id = item['agency']
            link = item['link']
            title = item['title']
            published_at = item.get('published_at')
            
            # Check DB Deduplication (Critical Step)
            if supabase:
                try:
                    # Check by Link first
                    existing = supabase.table('articles').select('id').eq('link', link).execute()
                    if existing.data and len(existing.data) > 0:
                        logger.debug(f"Skipping duplicate (DB link match): {title[:30]}...")
                        continue
                        
                    # Optional: Check by Title + Date if link might vary?
                    # For now link is best unique key.
                except Exception as e:
                    logger.error(f"DB Check failed: {e}")

            logger.info(f"Processing: [{agency_id}] {title}")
            
            # Scrape Detail Content
            agency_config = agency_map.get(agency_id)
            content = None
            
            # For RSS, we might not have content yet. For Scraper, we definitely don't (fetch_list only gets title).
            # Always try to fetch content if agency_config has selector
            if agency_config:
                content = scraper.fetch_content(link, agency_config)
                if content:
                    item['content'] = content
                else:
                    # Fallback
                    content = title + "\n" + item.get('description', '')

            # 3. Analyze
            analysis_result = None
            if analyzer:
                # logger.info("  > Analyzing...")
                analysis_result = analyzer.process(
                    {'title': title, 'content': content, 'description': item.get('description', '')},
                    agency_config.get('name', agency_id)
                )
                item['analysis_result'] = analysis_result
            
            # 4. Save to DB
            if supabase:
                try:
                    data = {
                        "agency": agency_id,
                        "title": title,
                        "link": link,
                        "published_at": published_at or datetime.now().isoformat(),
                        "content": content or "",
                        "analysis_result": analysis_result
                    }
                    supabase.table("articles").insert(data).execute()
                    logger.info("  > Saved to DB.")
                except Exception as e:
                    logger.error(f"  > Failed to save to DB: {e}")

            # 5. Notify
            if notifier and analysis_result and analysis_result.get('analysis_status') == 'ANALYZED':
                a_name = agency_config.get('name', agency_id)
                logger.info("  > Sending Notification...")
                notifier.format_and_send(a_name, title, link, analysis_result)
            
        logger.info("Cycle completed successfully.")
    except Exception as e:
        logger.error(f"Error in run_cycle: {e}")

    except Exception as e:
        logger.error(f"Error in run_cycle: {e}")

if __name__ == "__main__":
    run_cycle()

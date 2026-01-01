import sys
import os
import logging
from datetime import datetime, timedelta
import pytz

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # For config

from pipeline import Pipeline
from config import settings

AGENCY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'agencies.json')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BackfillPipeline(Pipeline):
    def __init__(self, days_back=365):
        super().__init__(config_path=AGENCY_CONFIG_PATH)
        self.days_back = days_back
        self.notifier = None # Disable notifications
        
    def _get_last_crawled_date(self, agency_code):
        # Override to force 1 year lookback
        kst = pytz.timezone('Asia/Seoul')
        return datetime.now(kst) - timedelta(days=self.days_back)
        
    def run_backfill(self):
        targets = ['FSS_REG', 'FSC_REG']
        logger.info(f"Starting Backfill for {targets} (Last {self.days_back} days)")
        
        all_items = []
        
        for agency_code in targets:
            base_config = self.agency_map.get(agency_code)
            if not base_config:
                logger.error(f"Config not found for {agency_code}")
                continue
                
            cutoff_date = self._get_last_crawled_date(agency_code)
            logger.info(f"Fetching {agency_code} since {cutoff_date.date()}...")
            
            # Pagination Loop
            page_param = 'pageIndex' if 'FSS' in agency_code else 'curPage'
            base_url = base_config['url']
            
            for page in range(1, 101): # Max 100 pages (approx 1000 items)
                # Clone config
                current_config = base_config.copy()
                sep = '&' if '?' in base_url else '?'
                current_config['url'] = f"{base_url}{sep}{page_param}={page}"
                
                try:
                    logger.info(f"  > Page {page}...")
                    items = self.scraper.fetch_list_items(current_config, last_crawled_date=cutoff_date)
                    
                    if not items:
                        logger.info(f"  > No new items on Page {page}. Stopping {agency_code}.")
                        break
                        
                    logger.info(f"  > Found {len(items)} items on Page {page}")
                    all_items.extend(items)
                    
                    # Safety break if too many
                    if len(all_items) > 500: # Limit per run safety
                         logger.warning("Safety limit (500) reached.")
                         # break # Optional: Uncomment to limit
                    
                except Exception as e:
                    logger.error(f"Failed to fetch {agency_code} page {page}: {e}")
                    break
                
        logger.info(f"Total items to process: {len(all_items)}")
        
        # Process items
        for i, item in enumerate(all_items):
            logger.info(f"Processing {i+1}/{len(all_items)}: {item['title']}")
            self._process_single_item(item)
            
        logger.info("Backfill Complete")

if __name__ == "__main__":
    # Ensure DB column exists first!
    print("WARNING: Assuming 'v2_add_category_column.sql' has been run.")
    # confirm = input("Type 'yes' to continue: ")
    # if confirm.lower() == 'yes':
    pipeline = BackfillPipeline(days_back=30)
    pipeline.run_backfill()
    # else:
    #     print("Aborted.")

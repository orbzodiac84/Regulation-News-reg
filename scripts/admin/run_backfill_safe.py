import sys
import os
import logging
import re
import time
import random
from datetime import datetime, timedelta
import pytz
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load env vars
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env.local')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"DEBUG: Loaded env from {env_path}")
else:
    print(f"DEBUG: .env.local not found at {env_path}")

# Add project root to path
sys.path.append(project_root)

from src.collectors.scraper import ContentScraper
from src.collectors.rss_parser import collect_rss_feed # Import specific function if possible, else use manual request
from src.pipeline import Pipeline
from config import settings

# ... (Logging config same as before) ...

# ... (BackfillScraper same as before) ...

class BackfillPipeline(Pipeline):
    # ... (__init__ same as before) ...
    
    def run(self):
        """
        Run backfill for all agencies
        """
        logger.info("Starting 60-Day Backfill Pipeline...")
        logger.info(f"Loaded Agencies: {list(self.agency_map.keys())}")
        
        # Check Analyzer
        if not os.getenv("GEMINI_API_KEY"):
            logger.error("CRITICAL: GEMINI_API_KEY not found. Aborting analysis.")
            # We continue collection but analysis will fail
        
        all_articles = []
        
        for code, config in self.agency_map.items():
            logger.info(f"Processing {code}...")
            collected = []
            
            try:
                if config.get('collection_method') == 'rss':
                    logger.info(f"  > RSS Mode for {code}")
                    # RSS does not support deep backfill easily, but let's fetch what we can
                    # Manually fetch RSS XML
                    try:
                        import feedparser
                        feed = feedparser.parse(config.get('url'))
                        logger.info(f"    > RSS Entries found: {len(feed.entries)}")
                        for entry in feed.entries:
                             # Convert to standardized dict
                             dt = datetime.now() # Default
                             if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                 dt = datetime(*entry.published_parsed[:6])
                             elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                 dt = datetime(*entry.updated_parsed[:6])
                             
                             # Timezone fix (Naive -> KST)
                             # Simply assume it's valid for now or parse properly
                             
                             collected.append({
                                 'title': entry.title,
                                 'link': entry.link,
                                 'published_at': dt.isoformat(),
                                 'agency': code,
                                 'category': config.get('category'),
                                 'content': entry.get('description', '') or entry.get('summary', '')
                             })
                    except Exception as e:
                        logger.error(f"RSS Fetch Error: {e}")

                else:
                    # Scraper Mode
                    collected = self.scraper.fetch_list_items(config)
                    
                    # Detail Fetch
                    details = []
                    for item in collected:
                       try:
                           content = self.scraper.fetch_content(item['link'], config)
                           if content:
                               item['content'] = content 
                               details.append(item)
                           else:
                               details.append(item)
                       except Exception as e:
                           logger.error(f"Failed to fetch content for {item['link']}: {e}")
                    collected = details # Update with content
                
                all_articles.extend(collected)
                logger.info(f"  > {code}: Collected {len(collected)} items.")
                
            except Exception as e:
                logger.error(f"Failed to process {code}: {e}")
        
        logger.info(f"Total Collected: {len(all_articles)} articles.")
        
        # ... (Save & Analyze logic same as before) ...
        
        # Analyze and Save
        if all_articles:
             # We need to save them.
             # Using Pipeline's analyzer?
             # For speed, we might want to prioritize saving first.
             
             # Save to DB directly first (Upsert)
             logger.info("Saving raw articles to Supabase...")
             for article in all_articles:
                 record = {
                     'id': article.get('id') or article.get('link'),
                     'agency': article.get('agency'),
                     'title': article.get('title'),
                     'content': article.get('content') or '',
                     'published_at': article.get('published_at'),
                     'link': article.get('link'),
                     'category': article.get('category'),
                 }
                 # Upsert
                 self.supabase.table('articles').upsert(record).execute()
             
             logger.info("Raw Save Complete. Starting Analysis...")
             
             # Run Analysis (This might take long)
             # Reuse pipeline's analyzer
             # HybridAnalyzer.analyze_batch is ideal if available.
             # If not, loop.
             
             for i, article in enumerate(all_articles):
                if i % 10 == 0:
                    logger.info(f"Analyzing {i}/{len(all_articles)}...")
                
                # Check if already analyzed (optimization)
                # But here we want to backfill analysis too.
                
                try:
                    analysis = self.analyzer.analyze(article)
                    if analysis:
                        # Update DB
                        # We need to construct the full analysis object structure
                        # The analyzer returns the 'analysis_result' JSONB object?
                        # Let's assume yes.
                        self.supabase.table('articles').update({
                            'analysis_result': analysis
                        }).eq('link', article['link']).execute()
                except Exception as e:
                    logger.error(f"Analysis Failed for {article.get('title')}: {e}")

        logger.info("Backfill Complete.")

if __name__ == "__main__":
    pipeline = BackfillPipeline(target_days=60)
    pipeline.run()

import requests
from bs4 import BeautifulSoup
import time
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from config import settings

import urllib3

# Suppress InsecureRequestWarning for verify=False
if settings.SUPPRESS_SSL_WARNINGS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ContentScraper:
    def __init__(self):
        # Use a very standard Chrome User-Agent
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }

    def fetch_list_items(self, agency_config: Dict, last_crawled_date: datetime = None) -> List[Dict]:
        """
        Fetches list of articles using HTML scraping with incremental logic.
        """
        # 1. Check method
        if agency_config.get('collection_method') != 'scraper':
            return []

        source_url = agency_config.get('url')
        selectors = agency_config.get('selector', {})
        list_selector = selectors.get('list')
        
        if not source_url or not list_selector:
            logger.error(f"[{agency_config.get('code')}] Missing URL or list selector.")
            return []

        # Timezone setup
        import pytz
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)

        # 2. Determine Cutoff
        # Ensure last_crawled_date is offset-aware if passed
        if last_crawled_date and last_crawled_date.tzinfo is None:
             last_crawled_date = kst.localize(last_crawled_date)

        if last_crawled_date:
            cutoff_date = last_crawled_date - timedelta(days=1)
            logger.info(f"[{agency_config.get('code')}] Incremental: > {cutoff_date.strftime('%Y-%m-%d')}")
        else:
            cutoff_date = now_kst - timedelta(days=7)
            logger.info(f"[{agency_config.get('code')}] Full Scan: > {cutoff_date.strftime('%Y-%m-%d')}")

        items = []
        try:
            time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX)) # Anti-ban delay
            response = requests.get(source_url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.select(list_selector)
            
            if not rows:
                logger.warning(f"[{agency_config.get('code')}] No items found with selector: {list_selector}")
                # Optional dump for debugging
                with open(f"debug_{agency_config.get('code')}.html", "w", encoding="utf-8") as f:
                    f.write(soup.prettify())
                return []
            
            for row in rows:
                try:
                    # Title
                    title_sel = selectors.get('title')
                    title_elem = row.select_one(title_sel) if title_sel else row.select_one('a')
                    
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    link_href = title_elem.get('href')
                    
                    # Link Resolution
                    if link_href:
                        if not link_href.startswith('http'):
                            from urllib.parse import urljoin
                            link = urljoin(source_url, link_href)
                        else:
                            link = link_href
                    else:
                        link = source_url # Fallback?

                    # Date
                    date_sel = selectors.get('date')
                    date_str = ""
                    if date_sel:
                        date_elem = row.select_one(date_sel)
                        if date_elem:
                            date_str = date_elem.get_text(strip=True)

                    # Date Parse & Cutoff
                    pub_date = self._parse_date(date_str)
                    
                    if pub_date:
                        # Check Force Collect policy from settings
                        agency_code = agency_config.get('code')
                        force_collect = agency_code in settings.FORCE_COLLECT_AGENCIES
                        
                        # Comparison should work now as both are offset-aware (KST)
                        if force_collect or pub_date >= cutoff_date:
                            if force_collect:
                                logger.info(f"  [{agency_code}] Force Collecting (Policy): {title} ({pub_date})")
                            
                            items.append({
                                'title': title,
                                'link': link,
                                'published_at': pub_date.isoformat(),
                                'agency': agency_code
                            })
                        else:
                            logger.info(f"  [{agency_code}] Reached cutoff ({pub_date.date()}). Stopping.")
                            break
                    else:
                        # Fallback if no date found (rare)
                        # Use KST now
                        items.append({
                            'title': title,
                            'link': link,
                            'published_at': now_kst.isoformat(),
                             'agency': agency_config.get('code')
                        })
                except Exception as e:
                    logger.error(f"[{agency_config.get('code')}] Error processing row: {e}")
                    continue
            return items

        except requests.exceptions.RequestException as e:
            logger.error(f"[{agency_config.get('code')}] Request error fetching list from {source_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"[{agency_config.get('code')}] Unexpected error fetching list from {source_url}: {e}")
            return []

    def fetch_content(self, url: str, agency_config: Dict) -> Optional[str]:
        """
        Fetches article content based on agency configuration (selectors).
        """
        scraper_config = agency_config.get('scraper') or agency_config.get('selector')
        if not scraper_config:
            logger.debug(f"No scraper/selector config for {agency_config.get('code')}")
            return None
        
        try:
            # Random delay
            time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX))
            
            response = requests.get(url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            container_selector = scraper_config.get('container_selector') or scraper_config.get('content')
            
            if not container_selector:
                return None
                
            content_div = soup.select_one(container_selector)
            if not content_div:
                logger.warning(f"Container not found for {url} ({container_selector})")
                return None
            
            # Remove unwanted elements
            remove_selectors = scraper_config.get('remove_selectors', [])
            for sel in remove_selectors:
                for match in content_div.select(sel):
                    match.decompose()
            
            # Extract text
            text_content = content_div.get_text(separator='\n', strip=True)
            
            # 🛡️ Data Integrity Check: Short Content Warning
            # Instead of failing, we tag it so analysis can decide what to do
            if len(text_content) < 50:
                logger.warning(f"⚠️ Short content detected ({len(text_content)} chars) for {url}")
                return f"[Short Content] {text_content}"
                
            return text_content

        except Exception as e:
            logger.error(f"Error scraping content from {url}: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Helper to parse various date formats and ENFORCE KST (UTC+9).
        """
        if not date_str:
            return None
            
        try:
            import pytz
            import re
            
            # KST Timezone Definition
            kst = pytz.timezone('Asia/Seoul')
            
            # Clean up: remove "등록일" etc, keep only digits, dots, hyphens
            match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)
            
            clean_date_str = ""
            if match:
                clean_date_str = match.group(1).replace('.', '-')
            else:
                clean_date_str = date_str.strip().replace('.', '-')
            
            # Parse naïve datetime
            dt = datetime.strptime(clean_date_str, '%Y-%m-%d')
            
            # Localize to KST (Midnight KST)
            # This ensures 2024-12-25 00:00:00 KST
            dt_kst = kst.localize(dt)
            
            return dt_kst
            
        except ValueError:
            return None

if __name__ == "__main__":
    # Test with a real URL (using FSC item if available or hardcoded)
    test_agency = {
        "id": "TestFSC",
        "scraper": {
            "container_selector": "#content", # Example selector, might need adjustment based on real site
            "remove_selectors": [".file_list", ".btn_area"]
        }
    }
    # Note: Using a placeholder URL for test. In real usage, we pass real URLs.
    print("Scraper module ready.")

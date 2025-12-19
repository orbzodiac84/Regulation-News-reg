import requests
from bs4 import BeautifulSoup
import time
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ContentScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def fetch_content(self, url: str, agency_config: Dict) -> Optional[str]:
        """
        Fetches article content based on agency configuration (selectors).
        Supports both 'selector' (new) and 'scraper' (old) keys.
        """
        # Support new schema 'selector' or old 'scraper'
        # New schema: selector: { "container": "..." } or implied?
        # The prompt examples didn't specify container selector for details, only list/title/date.
        # But we need content. If not provided, we might fall back to whole body or common logic?
        # Wait, the prompt json didn't have 'container_selector'.
        # I'll check if I added it. Step 1856 JSON: list, title, date... no content/container.
        # For now, I'll rely on 'scraper' key IF present, OR try to find 'content' key in 'selector'.
        
        scraper_config = agency_config.get('scraper') or agency_config.get('selector')
        if not scraper_config:
            logger.debug(f"No scraper/selector config for {agency_config.get('code')}")
            return None
        
        try:
            # Random delay
            time.sleep(random.uniform(0.5, 1.5))
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Helper to get container_selector
            # In new schema, maybe we add 'content' key to selector?
            # Or use a default.
            container_selector = scraper_config.get('container_selector') or scraper_config.get('content')
            
            if not container_selector:
                # Attempt generic extraction if no selector
                # Or just return None
                return None
                
            content_div = soup.select_one(container_selector)
            if not content_div:
                print(f"Container not found for {url} ({container_selector})")
                return None
            
            # Remove unwanted elements
            remove_selectors = scraper_config.get('remove_selectors', [])
            for sel in remove_selectors:
                for match in content_div.select(sel):
                    match.decompose()
            
            # Extract text
            text = content_div.get_text(separator='\n', strip=True)
            return text

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

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

        # 2. Determine Cutoff
        if last_crawled_date:
            cutoff_date = last_crawled_date - timedelta(days=1)
            logger.info(f"[{agency_config.get('code')}] Incremental: > {cutoff_date.strftime('%Y-%m-%d')}")
        else:
            cutoff_date = datetime.now() - timedelta(days=7)
            logger.info(f"[{agency_config.get('code')}] Full Scan: > {cutoff_date.strftime('%Y-%m-%d')}")

        items = []
        try:
            time.sleep(random.uniform(2.0, 4.0)) # Anti-ban delay
            response = requests.get(source_url, headers=self.headers, timeout=20, verify=False)
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
                    
                    # If date parsing failed, we might want to default to now() or skip cutoff
                    # But for safety, if we can't parse date, we treat it as "new" generally, 
                    # OR we might log a warning.
                    
                    if pub_date:
                        if pub_date < cutoff_date:
                            logger.info(f"  [{agency_config.get('code')}] Reached cutoff ({pub_date.date()}). Stopping.")
                            break # List is usually ordered by date desc
                        
                        items.append({
                            'title': title,
                            'link': link,
                            'published_at': pub_date.isoformat(),
                            'agency': agency_config.get('code') # ID
                        })
                    else:
                        # Fallback if no date found (rare)
                        items.append({
                            'title': title,
                            'link': link,
                            'published_at': datetime.now().isoformat(),
                             'agency': agency_config.get('code')
                        })

                except Exception as row_e:
                    logger.debug(f"Row parsing error: {row_e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping {source_url}: {e}")
            
        return items

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Helper to parse various date formats.
        """
        if not date_str:
            return None
            
        try:
            # Clean up: remove "등록일" etc, keep only digits, dots, hyphens
            # Simplest: Regex find pattern YYYY.MM.DD or YYYY-MM-DD
            import re
            match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)
            if match:
                date_str = match.group(1).replace('.', '-')
                return datetime.strptime(date_str, '%Y-%m-%d')
                
            # Fallback for plain replacement if regex misses (unlikely but safe)
            date_str = date_str.strip().replace('.', '-')
            return datetime.strptime(date_str, '%Y-%m-%d')
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

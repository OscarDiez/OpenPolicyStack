
import logging
import time
from typing import List, Dict, Any
try:
    from googlesearch import search
except ImportError:
    search = None

logger = logging.getLogger("SocialScraper")

class SocialScraper:
    def __init__(self):
        self.platforms = {
            "twitter": "site:twitter.com",
            "instagram": "site:instagram.com",
            "facebook": "site:facebook.com",
            "tiktok": "site:tiktok.com"
        }
        self.risk_keywords = [
            "corrupcion", "fraude", "estafa", "denuncia", "robo", 
            "preso", "carcel", "delito", "soborno"
        ]

    def get_social_intelligence(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Scrape social media mentions using Google Dorks (OSINT).
        Searches for {query} + {risk_keywords} on major platforms.
        """
        if not search:
            logger.warning("googlesearch-python not installed. Skipping social scrape.")
            return []

        hits = []
        logger.info(f"🔎 Scanning social media for: {query}...")
        
        for platform, site_operator in self.platforms.items():
            # Construct a complex query: site:twitter.com "Juan Perez" (corrupcion OR fraude)
            risk_query = " OR ".join(self.risk_keywords[:3]) # Keep it short for query limits
            full_query = f'{site_operator} "{query}" ({risk_query}) "Republica Dominicana"'
            
            try:
                # search() yields URLs
                for url in search(full_query, num_results=limit, lang="es"):
                    hits.append({
                        "platform": platform,
                        "title": f"Mention on {platform.title()}", # Google search result doesn't give title easily in this lib, but URL is decent
                        "url": url,
                        "risk_score": 30, # Base risk for appearing in this context
                        "source": "OSINT Social Search"
                    })
                    time.sleep(1) # Rate limit protection
            except Exception as e:
                logger.error(f"Error searching {platform}: {e}")
                
        # Deduplicate
        unique_hits = {h['url']: h for h in hits}.values()
        return list(unique_hits)

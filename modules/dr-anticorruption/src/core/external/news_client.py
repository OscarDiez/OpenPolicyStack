
import logging
import time
import requests
import urllib.parse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime
from src.config.config import config

logger = logging.getLogger("NewsClient")

class NewsClient:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.region = config.get('news.region', 'DO')
        self.language = config.get('news.language', 'es-419')
        self.risk_keywords = config.get('keywords.risk_news', [])

    def search_entity(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search Google News RSS for an entity/query.
        Returns a list of structured hits with risk scoring.
        """
        encoded_query = urllib.parse.quote(query)
        # ceid specifies country and language (e.g., DO:es-419)
        url = f"{self.base_url}?q={encoded_query}&hl={self.language}&gl={self.region}&ceid={self.region}:{self.language}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return self._parse_rss(response.text, limit)
        except Exception as e:
            logger.error(f"Failed to fetch news for '{query}': {e}")
            return []

    def _parse_rss(self, xml_content: str, limit: int) -> List[Dict[str, Any]]:
        hits = []
        try:
            soup = BeautifulSoup(xml_content, 'xml')
            items = soup.find_all('item')
            
            for item in items[:limit]:
                title = item.title.text if item.title else "No Title"
                link = item.link.text if item.link else ""
                pub_date = item.pubDate.text if item.pubDate else ""
                
                # Basic risk scoring based on title
                risk_score = self._calculate_risk_score(title)
                
                hits.append({
                    "title": title,
                    "url": link,
                    "published_at": pub_date,
                    "risk_score": risk_score,
                    "source": "Google News RSS"
                })
        except Exception as e:
            logger.error(f"Error parsing RSS XML: {e}")
            
        return hits

    def _calculate_risk_score(self, text: str) -> int:
        """
        Score a headline based on presence of corruption keywords.
        """
        text_lower = text.lower()
        
        # Filter out irrelevance
        exclude_terms = ["horoscopo", "lotería", "beisbol", "nba", "mlb", "pelicula", "novela"]
        if any(term in text_lower for term in exclude_terms):
            return 0

        score = 0
        
        for kw in self.risk_keywords:
            if kw.lower() in text_lower:
                score += 10
                
        # Boost for strong phrases
        if "procuradur" in text_lower or "pepca" in text_lower:
            score += 20
        if "arrest" in text_lower or "prision" in text_lower:
            score += 15
            
        return min(score, 100)

"""
News Scraper POC
Validates feasibility of fetching corruption-related news from Google News RSS.
Target: Dominican Republic context.
"""

import requests
import xml.etree.ElementTree as ET

def check_news(query):
    # Search Dominican Republic news (gl=DO, ceid=DO:es-419)
    base_url = "https://news.google.com/rss/search"
    params = {
        "q": query,
        "hl": "es-419",
        "gl": "DO",
        "ceid": "DO:es-419"
    }
    
    try:
        print(f"🔍 Searching news for: '{query}'...")
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        
        print(f"✅ Found {len(items)} articles.")
        print("-" * 50)
        
        for i, item in enumerate(items[:5]):
            title = item.find('title').text
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            print(f"{i+1}. {title}")
            print(f"   📅 {pubDate}")
            print(f"   🔗 {link}\n")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test 1: General Corruption
    check_news("Republica Dominicana Corrupcion")
    
    # Test 2: Procuraduría
    check_news("Procuraduría General Republica Dominicana")

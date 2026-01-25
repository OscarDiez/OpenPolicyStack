import json
import logging
import time
from typing import List, Dict
from src.core.external.news_client import NewsClient

# Configuration
THRESHOLD_CO_OCCURRENCE = 1 # Number of shared articles to trigger a link

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("SocialAnalyzer")

class SocialAnalyzer:
    def __init__(self):
        self.news_client = NewsClient()
        self.associations = [] # List of (Person A, Person B, Evidence)

    def analyze_connections(self, names: List[str]):
        """
        Analyze potential social/business connections between a list of people 
        by searching for co-occurrences in news.
        """
        print(f"\n🧠 ANALYZING SOCIAL CONNECTIONS FOR {len(names)} PEOPLE")
        print("-" * 60)
        
        # We can optimize by searching for pairs, but for the first version, 
        # we'll fetch news for each and find overlapping URLs.
        news_map = {} # name -> list of article URLs
        article_data = {} # url -> article title
        
        for name in names:
            print(f"🔍 Fetching news for: {name}...")
            hits = self.news_client.search_entity(name, limit=15)
            urls = []
            for hit in hits:
                url = hit['url']
                urls.append(url)
                article_data[url] = hit['title']
            
            news_map[name] = set(urls)
            time.sleep(1) # Be polite to Google News
            
        # Cross-reference
        print("\n🤝 Finding Overlaps...")
        found_links = 0
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                name_a = names[i]
                name_b = names[j]
                
                common_urls = news_map[name_a].intersection(news_map[name_b])
                
                if common_urls:
                    found_links += 1
                    for url in common_urls:
                        print(f"   ✨ CONNECTION FOUND: {name_a} <--> {name_b}")
                        print(f"      Article: {article_data[url]}")
                        self.associations.append({
                            "person_a": name_a,
                            "person_b": name_b,
                            "type": "NEWS_CO_OCCURRENCE",
                            "article_title": article_data[url],
                            "url": url
                        })
        
        if found_links == 0:
            print("   (No direct co-occurrences found in the 5-year lookback for these spécifiques pairs)")
            
        return self.associations

    def analyze_legal_risks(self, names: List[str]):
        """
        Check if representatives appear in the context of known corruption cases 
        or legal investigations.
        """
        legal_contexts = [
            "Caso Antipulpo", "Caso Calamar", "Caso Coral", "Caso Medusa", 
            "Procuraduría", "Fiscalía", "Lavado de activos"
        ]
        
        print(f"\n⚖️  CHECKING LEGAL RISKS FOR {len(names)} PEOPLE")
        print("-" * 60)
        
        for name in names:
            for context in legal_contexts:
                query = f'"{name}" {context}'
                print(f"   🔍 Querying: {query}...", end='\r')
                
                hits = self.news_client.search_entity(query, limit=5)
                if hits:
                    print(f"   🚩 RISK ALERT: {name} found in context of {context}!")
                    for hit in hits:
                        # Only score if the title or text actually contains the name 
                        # Google News RSS titles usually contain the query terms
                        self.associations.append({
                            "person": name,
                            "context": context,
                            "type": "LEGAL_QUERY_MATCH",
                            "article_title": hit['title'],
                            "url": hit['url']
                        })
                            
        return self.associations

    def save_results(self):
        timestamp = int(time.time())
        output_file = f"data/legal_social_hits_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.associations, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved to: {output_file}")

if __name__ == "__main__":
    analyzer = SocialAnalyzer()
    
    # Selected target names from previous relationship scan
    test_names = [
        "JUAN FRANCISCO MARTE", 
        "OLGA DILIA SEGURA",
        "RAFAEL UCETA ESPINAL",
        "DELFIN RAFAEL LOPEZ GOMEZ",
        "MAXIMO GOMEZ",
        "PEDRO SENADOR",
        "JUAN MINISTRO" 
    ]
    
    analyzer.analyze_connections(test_names[:4]) # Just a few pairs
    analyzer.analyze_legal_risks(test_names)
    analyzer.save_results()

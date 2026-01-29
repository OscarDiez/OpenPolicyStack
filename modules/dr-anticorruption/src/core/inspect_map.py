
import requests
from bs4 import BeautifulSoup
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

def inspect():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url = 'https://map.gob.do/transparencia/'
    
    try:
        print(f"Fetching {url}...")
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        print(f"Status Code: {r.status_code}")
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Analyze menu structure (usually 'Nómina', 'Recursos Humanos')
            print("\n--- Key Menu Items ---")
            links = soup.find_all('a')
            keywords = ['nómina', 'nomina', 'funcionarios', 'empleados', 'recursos humanos', 'datos abiertos', 'organigrama']
            
            seen = set()
            for l in links:
                text = l.get_text().strip().lower()
                href = l.get('href')
                if href and Any(k in text for k in keywords):
                    if href not in seen:
                        print(f"FOUND: {l.get_text().strip()} -> {href}")
                        seen.add(href)
                        
            # Analyze if there is a 'Download' section
            print("\n--- Downloadable Files ---")
            for l in links:
                href = l.get('href')
                if href and (href.endswith('.pdf') or href.endswith('.xls') or href.endswith('.xlsx') or href.endswith('.csv')):
                    print(f"FILE: {l.get_text().strip()} -> {href}")

        else:
            print(f"Failed to access page. Content snippet:\n{r.text[:500]}")

    except Exception as e:
        print(f"Critical Error: {e}")

def Any(iterable):
    for element in iterable:
        if element:
            return True
    return False

if __name__ == "__main__":
    inspect()

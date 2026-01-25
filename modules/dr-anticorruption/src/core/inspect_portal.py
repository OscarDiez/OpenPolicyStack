
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = 'https://consultadjp.camaradecuentas.gob.do/'
try:
    print(f'Fetching {url}...')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    r = requests.get(url, headers=headers, timeout=10, verify=False)
    print(f'Status: {r.status_code}')
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # diverse checks
    print("inputs:")
    all_inputs = soup.find_all('input')
    for i in all_inputs:
        print(f"  - Tag: input, ID: {i.get('id')}, Name: {i.get('name')}, Class: {i.get('class')}")
        
    print("buttons:")
    all_buttons = soup.find_all('button')
    for b in all_buttons:
        print(f"  - Tag: button, ID: {b.get('id')}, Text: {b.get_text().strip()}, OnClick: {b.get('onclick')}")

    # Check for 'a' tags that look like buttons
    all_links = soup.find_all('a', class_='btn')
    for a in all_links:
        print(f"  - Tag: a (btn), ID: {a.get('id')}, Text: {a.get_text().strip()}, Href: {a.get('href')}, OnClick: {a.get('onclick')}")

        
    # Check for scripts like 'app.js' or similar that might hint at an SPA
    scripts = soup.find_all('script', src=True)
    print(f'Found {len(scripts)} scripts.')
    for s in scripts:
        print(f'- Src: {s["src"]}')

    # Look for API-like scripts or config
    print("\nPage Text Snippet (first 500 chars):")
    print(soup.get_text()[:500].strip())
        
except Exception as e:
    print(f'Error: {e}')

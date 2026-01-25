
import requests
from bs4 import BeautifulSoup
import urllib3
import logging

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO)

def fetch_real_payroll():
    # MEPYD is a reliable source for open data payrolls
    base_url = 'https://mepyd.gob.do/transparencia/recursos-humanos/nomina-de-empleados/'
    
    try:
        logging.info(f"Scanning {base_url}...")
        r = requests.get(base_url, verify=False, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        
        if r.status_code != 200:
            logging.error(f"Failed to load page: {r.status_code}")
            return

        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        downloaded = False
        for a in links:
            href = a['href']
            if href.endswith('.xlsx') or href.endswith('.xls'):
                logging.info(f"FOUND REAL DATA: {href}")
                
                try:
                    r2 = requests.get(href, verify=False, timeout=30)
                    if r2.status_code == 200:
                        filename = "data/raw/nomina_real_sample.xlsx"
                        with open(filename, 'wb') as f:
                            f.write(r2.content)
                        logging.info(f"Successfully downloaded real payroll to {filename}")
                        downloaded = True
                        break
                except Exception as ex:
                    logging.warning(f"Download failed for {href}: {ex}")

        if not downloaded:
            logging.warning("No Excel files found on the transparency page.")

    except Exception as e:
        logging.error(f"Critical error: {e}")

if __name__ == "__main__":
    fetch_real_payroll()

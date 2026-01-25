import requests
from bs4 import BeautifulSoup
import logging
from typing import List

logger = logging.getLogger(__name__)

class ShareholderScraper:
    def __init__(self):
        self.base_url = "https://www.dgcp.gob.do/constancia/descargar"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def fetch_certification_html(self, cert_code: str) -> str:
        url = f"{self.base_url}/{cert_code}"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch cert {cert_code}: {e}")
            return None

    def extract_shareholders(self, html_content: str) -> List[str]:
        if not html_content:
            return []
        soup = BeautifulSoup(html_content, 'html.parser')
        shareholders = []
        # SPA app, data in JS. Use Puppeteer for render.
        # TODO: Integrate browser_action or selenium for JS render
        # Selectors from debug_cert_page.html or JS parse
        # Placeholder
        tables = soup.find_all('table', class_='list')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                name_cell = row.find(class_='name')
                if name_cell:
                    shareholders.append(name_cell.text.strip())
        logger.info(f"Extracted {len(shareholders)} shareholders")
        return shareholders

# Note: DGCP cert page is SPA, requires JS execution. Use Puppeteer.

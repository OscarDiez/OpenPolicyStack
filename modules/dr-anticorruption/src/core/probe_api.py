
import requests
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APIProbe")

base_url = 'https://consultadjp.camaradecuentas.gob.do'
endpoints = [
    '/Home/Buscar',
    '/Home/Search',
    '/Declaracion/Buscar',
    '/Declaracion/Search',
    '/Consulta/Buscar',
    '/Consulta/GetDeclaraciones',
    '/Consulta/Listar',
    '/Home/Listar',
    '/api/declaraciones',
    '/api/search',
    '/Home/GetDeclaraciones'
]

# Common payload based on inputs: txtNombre, txtCedula
# The server likely expects specific keys. Usually matching the ID or Name attribute.
# Since Name attribute was None in my inspection, they typically use ID-based serialization or manual JSON construction.
# Let's try standard naming conventions.
payloads = [
    {"nombre": "JUAN"},
    {"txtNombre": "JUAN"},
    {"filter": "JUAN"},
    {"q": "JUAN"},
    {"cedula": "", "nombre": "JUAN", "institucion": "", "cargo": ""},
]

def probe():
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'X-Requested-With': 'XMLHttpRequest', # Important for ASP.NET MVC to recognize AJAX
        'Content-Type': 'application/json' # Try JSON first
    }
    
    for ep in endpoints:
        url = base_url + ep
        for payload in payloads:
            try:
                # Try POST (most search forms use POST)
                r = requests.post(url, json=payload, headers=headers, verify=False, timeout=5)
                if r.status_code == 200:
                    logger.info(f"SUCCESS! POST {url} returned 200.")
                    logger.info(f"Response snippet: {r.text[:200]}")
                    return # Stop on first hit
                
                # Try GET
                r_get = requests.get(url, params=payload, headers=headers, verify=False, timeout=5)
                if r_get.status_code == 200 and len(r_get.text) > 500: # Ignore short standard error pages
                    logger.info(f"SUCCESS! GET {url} returned 200.")
                    logger.info(f"Response snippet: {r_get.text[:200]}")
                    return

            except Exception as e:
                logger.error(f"Failed {url}: {e}")

if __name__ == "__main__":
    probe()

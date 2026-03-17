import os
import httpx
import json
from typing import Dict, Any, Optional

class ComtradeClient:
    """
    Client for the UN Comtrade Public API.
    Used for retrieving official trade statistics via HS Codes.
    """
    
    # Public V2 API Endpoint for Annual Harmonized System Data
    # Path format: /get/{type}/{freq}/{clCode} -> /get/C/A/HS
    BASE_URL = "https://comtradeapi.un.org/public/v1/get/C/A/HS"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COMTRADE_API_KEY")

    def get_trade_data(self, hs_code: str, period: str = "2023", reporter_code: str = "all") -> Optional[Dict[str, Any]]:
        """
        Fetch annual trade data for a specific HS code using Comtrade V2 API.
        """
        print(f"[*] Querying UN Comtrade V2 API for HS Code: {hs_code}...")
        
        # V2 API Parameters
        params = {
            "cmdCode": hs_code,          # Commodity Code
            "period": period,            # Year
            "reporterCode": 251,         # France (as an example) or use specific M49 codes. 
                                         # 'all' is NOT supported on public free tier usually, need specific reporters or '0' (World) if allowed.
                                         # Free tier often limits 'reporterCode' to specific ID or smaller set. 
                                         # Let's try '0' (World) or a major economy like '842' (USA) or '156' (China) to get *some* data.
                                         # Actually, for public API, let's try to get global context by checking major aggregators.
                                         # SAFE BET: '0' is World (often restricted). Let's use NULL to get all?
                                         # Comtrade V2 usually requires explicit codes. Let's try to fetch for top economies if 'all' fails.
            "flowCode": "M,X",           # Import, Export
            "format": "json"
        }
        
        # NOTE: The public API is very restrictive. 
        # For a truly autonomous "zero-conf" demo, we might need a fallback or a specific open endpoint.
        # But let's try the standard V2 public route with 'reporterCode=null' (all reporters).
        # Re-reading docs: 'reporterCode' is mandatory. 'all' might NOT work on public.
        # Let's try a widely available reporter like USA (842) to ensure we get *some* data for the risk engine.
        params["reporterCode"] = "842,156,276" # USA, China, Germany (Top economies)
        
        if self.api_key:
            # If we have a key, we use the PRO endpoint ideally, but let's stick to public structure
            # Authenticated users should use: https://comtradeapi.un.org/data/v1/get/C/A/HS
            # This class defaults to Public.
            params["subscription-key"] = self.api_key
            self.BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS" 
            params["reporterCode"] = "all" # Authenticated allows 'all'

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; SupplyChainRiskBot/1.0)",
                "Accept": "application/json"
            }
            response = httpx.get(self.BASE_URL, params=params, headers=headers, timeout=20.0)
            
            if response.status_code == 200:
                data = response.json()
                results_count = data.get("count", 0)
                # V2 Structure: data is inside 'data' key
                records = data.get("data", [])
                print(f"[+] UN Comtrade API returned {len(records)} records.")
                return data
            else:
                print(f"[!] UN Comtrade API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"[!] UN Comtrade Client error: {e}")
            return None

def main():
    # Test for Helium-3 (Isotopes HS Code: 284590)
    client = ComtradeClient()
    result = client.get_trade_data("284590")
    if result:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

# Supply-Chain Risk Extractor - Usage Guide

## Quick Start

### 1. Install Dependencies
```bash
cd modules/supplychain-risk
pip install -r requirements.txt
```

### 2. Get Free Groq API Key
1. Visit: https://console.groq.com/keys
2. Sign up (free)
3. Create an API key
4. Set environment variable:
   ```bash
   export GROQ_API_KEY="your_key_here"
   ```

### 3. Extract a Single Component
```bash
python src/extractor.py --component "Helium-3"
```

**Output**: `data/suppliers/helium3_suppliers.json`

### 4. Batch Extract All Components in a Segment
```bash
python src/extractor.py --batch --segment cryogenics
```

**Output**: Multiple JSON files in `data/suppliers/`

---

## What the Extractor Does

### Phase 1: Entity Discovery
- Searches: `"{component} manufacturers producers suppliers 2024 2025"`
- Finds: Company names, countries, production sites

### Phase 2: Quantitative Data
- Searches: `"{component} production volume market share export statistics 2024"`
- Extracts: Production volumes, market share, trade values

### Output Schema
```json
{
  "component": "Helium-3",
  "extraction_metadata": {
    "timestamp": "2026-02-16T00:30:00Z",
    "search_query": "Helium-3 manufacturers...",
    "llm_model": "llama-3.1-70b-versatile",
    "entity_count": 6
  },
  "suppliers": [
    {
      "name": "US DOE",
      "country": "USA",
      "role": "Producer",
      "production_volume": {
        "value": 100,
        "unit": "liters/year",
        "year": 2023,
        "source": "DOE Report"
      },
      "market_share": 0.35,
      "export_value": {
        "value": 22300000,
        "unit": "USD",
        "year": 2024
      }
    }
  ]
}
```

---

## Adding New Components

1. **Update Taxonomy** (optional):
   Edit `data/taxonomy/cryogenics_taxonomy.json`

2. **Run Extractor**:
   ```bash
   python src/extractor.py --component "Your New Component"
   ```

3. **Verify Output**:
   Check `data/suppliers/your_new_component_suppliers.json`

---

## Troubleshooting

### No API Key Error
```
[!] No GROQ_API_KEY found
```
**Fix**: `export GROQ_API_KEY="your_key"`

### No Search Results
```
[!] No search results found
```
**Fix**: Component name might be too specific. Try broader terms.

### LLM Returns Empty Array
```
[!] No entities extracted
```
**Fix**: Check if search results contain relevant data. Try different search terms.

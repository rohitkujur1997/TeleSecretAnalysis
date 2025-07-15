#https://www.nseindia.com/api/equity-master
#https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET
#copy text to your_file.json and execute
#move generated csv to repo

import json
import csv
from datetime import datetime

# Load JSON data
with open("your_file.json", "r") as f:
    data = json.load(f)

# Extract required fields with date filter
results = []
cutoff_date = datetime.strptime("2015-01-01", "%Y-%m-%d")
remov = ['UNITDSPR', 'AEGISLOG', 'HBLENGINE', 'EMBDL']

for item in data["data"]:
    meta = item.get("meta", {})
    listing_date_str = meta.get("listingDate", item.get("listingDate", None))
    symbol_str = meta.get("symbol", item.get("symbol"))
    
    try:
        if listing_date_str:
            listing_date = datetime.strptime(listing_date_str, "%Y-%m-%d")
            if listing_date <= cutoff_date and symbol_str not in remov:
                entry = {
                    "symbol": meta.get("symbol", item.get("symbol")),
                    "companyName": meta.get("companyName", "N/A"),
                    "industry": meta.get("industry", "N/A"),
                    "isFNOSec": meta.get("isFNOSec", item.get("isFNOSec", False))
                }
                results.append(entry)
    except ValueError:
        # Skip rows with invalid date format
        continue

# Export to CSV
if results:
    csv_file = "output_data.csv"
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"Data exported to {csv_file}")
else:
    print("No matching data found.")

#https://www.nseindia.com/api/equity-master
#https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET
#copy text to your_file.json and execute
#move generated csv to repo

import json
import csv
from datetime import datetime


def callme1(i):
    # Load JSON data
    #print(i)
    with open(i, "r") as f:
        data = json.load(f)
        return data


def callme2(data,j):
    # Extract required fields with date filter
    results = []
    cutoff_date = datetime.strptime("2021-01-01", "%Y-%m-%d")
    remov = []

    for item in data["data"]:
        meta = item.get("meta", {})
        
        listing_date_str = meta.get("listingDate", item.get("listingDate", None))
        symbol_str = meta.get("symbol", item.get("symbol"))
        
        try:
            """ if listing_date_str:
                listing_date = datetime.strptime(listing_date_str, "%Y-%m-%d")
                if listing_date <= cutoff_date and symbol_str not in remov:
                    entry = {
                        "symbol": meta.get("symbol", item.get("symbol")),
                        "companyName": meta.get("companyName", "N/A"),
                        "industry": meta.get("industry", "N/A"),
                        "isFNOSec": meta.get("isFNOSec", item.get("isFNOSec", False))
                    }
                    results.append(entry) """
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
        csv_file = j#"NiftyMIDSMALLCAP400.csv"
        with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        print(f"Data exported to {csv_file}")
    else:
        print("No matching data found.")

ilist= ["NIFTY IT"]
""" ilist = [
    "NIFTY 50",
    "NIFTY NEXT 50",
    "NIFTY BANK",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY MIDCAP SELECT",
    "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50",
    "NIFTY SMALLCAP 100",
    "NIFTY SMALLCAP 250",
    "NIFTY MIDSMALLCAP 400",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY500 MULTICAP 50:25:25",
    "NIFTY LARGEMIDCAP 250",
    "NIFTY TOTAL MARKET",
    "NIFTY MICROCAP 250",
    "NIFTY 500",
    "NIFTY500 LARGEMIDSMALL EQUAL-CAP WEIGHTED",
    "NIFTY AUTO",
    "NIFTY FINANCIAL SERVICES 25/50",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY MEDIA",
    "NIFTY METAL",
    "NIFTY PHARMA",
    "NIFTY PSU BANK",
    "NIFTY REALTY",
    "NIFTY PRIVATE BANK",
    "NIFTY HEALTHCARE INDEX",
    "NIFTY CONSUMER DURABLES",
    "NIFTY OIL & GAS",
    "NIFTY MIDSMALL HEALTHCARE",
    "NIFTY FINANCIAL SERVICES EX-BANK",
    "NIFTY MIDSMALL FINANCIAL SERVICES",
    "NIFTY MIDSMALL IT & TELECOM",
    "NIFTY COMMODITIES",
    "NIFTY INDIA CONSUMPTION",
    "NIFTY CPSE",
    "NIFTY ENERGY",
    "NIFTY INFRASTRUCTURE",
    "NIFTY MNC",
    "NIFTY PSE",
    "NIFTY SERVICES SECTOR",
    "NIFTY100 LIQUID 15",
    "NIFTY MIDCAP LIQUID 15",
    "NIFTY INDIA DIGITAL",
    "NIFTY100 ESG",
    "NIFTY INDIA MANUFACTURING",
    "NIFTY INDIA CORPORATE GROUP INDEX - TATA GROUP 25% CAP",
    "NIFTY500 MULTICAP INDIA MANUFACTURING 50:30:20",
    "NIFTY500 MULTICAP INFRASTRUCTURE 50:30:20",
    "NIFTY INDIA DEFENCE",
    "NIFTY INDIA TOURISM",
    "NIFTY CAPITAL MARKETS",
    "NIFTY EV & NEW AGE AUTOMOTIVE",
    "NIFTY INDIA NEW AGE CONSUMPTION",
    "NIFTY INDIA SELECT 5 CORPORATE GROUPS (MAATR)",
    "NIFTY MOBILITY",
    "NIFTY100 ENHANCED ESG",
    "NIFTY CORE HOUSING",
    "NIFTY HOUSING",
    "NIFTY IPO",
    "NIFTY MIDSMALL INDIA CONSUMPTION",
    "NIFTY NON-CYCLICAL CONSUMER",
    "NIFTY RURAL",
    "NIFTY SHARIAH 25",
    "NIFTY TRANSPORTATION & LOGISTICS",
    "NIFTY50 SHARIAH",
    "NIFTY500 SHARIAH"
    ] """
for i in ilist:
    data = callme1(i+".json")
    #j=i.replace(".json",".csv")
    callme2(data,i+".csv")
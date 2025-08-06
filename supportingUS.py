import pandas as pd

url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
tables = pd.read_html(url)
df = tables[0]  # usually the main table
symbols = df['Symbol'].tolist()
df[['Symbol', 'Security', 'GICS Sector']].to_csv("Output_dataSNP500.csv", index=False)

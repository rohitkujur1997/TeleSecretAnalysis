import pandas as pd
import os
from glob import glob

# Set your directory path (e.g., "./csv_files/")
directory_path = 'D:/TeleAnalysis'  # change this to your path

#  Find all CSV files in the directory
csv_files = glob(os.path.join(directory_path, '*.csv'))

# Check if any CSV files found
if not csv_files:
    print("No CSV files found in the directory.")
    exit()

#  Read and concatenate all CSVs row-wise
all_data = []

for file in csv_files:
    try:
        df = pd.read_csv(file)
        all_data.append(df)
    except Exception as e:
        print(f"Error reading {file}: {e}")

# Combine rows and remove duplicates
combined_df = pd.concat(all_data, ignore_index=True)

# Save the final result
output_file = 'combined_output.csv'
combined_df.to_csv(output_file, index=False)

print(f"All rows concatenated successfully. Duplicates removed. Output saved to {output_file}.")

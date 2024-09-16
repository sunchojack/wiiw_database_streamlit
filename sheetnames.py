import pandas as pd
import pycountry

# Read all sheets into a dictionary of DataFrames
data = pd.read_excel('excel_defaults_mapped.xlsx', sheet_name=None)

# Get the sheet names (assuming they are 2-letter country codes)
sheets_export = list(data.keys())
print("Sheets (2-letter codes):", sheets_export)

# Create an empty list to store the matches
correspondence_table = []

# First, match the 2-letter codes to country names using pycountry
for ccode in sheets_export:
    country = pycountry.countries.get(alpha_2=ccode.upper())  # Ensure code is in uppercase for matching
    if country:
        # Append the code and the country name to the correspondence table
        correspondence_table.append({'code': ccode, 'name': country.name})
    else:
        correspondence_table.append({'code': ccode, 'name': 'No matching country found'})

# Now, match the country names from 'db_mapping' to their corresponding 2-letter codes
db_mapping = pd.read_csv('database_mapping.csv')['reporter'].unique()

for countryname in db_mapping:
    country = None
    try:
        country = pycountry.countries.lookup(countryname)  # Use lookup to match country name variations
    except LookupError:
        pass  # Ignore LookupError if no match is found

    if country:
        correspondence_table.append({'code': country.alpha_2, 'name': countryname})
    else:
        correspondence_table.append({'code': 'Not a sheet name', 'name': countryname})

# Convert the correspondence table to a DataFrame for better viewing and manipulation
correspondence_df = pd.DataFrame(correspondence_table)
correspondence_df = correspondence_df[correspondence_df['name'].isin(db_mapping)].drop_duplicates().sort_values('name')

# Print the resulting correspondence table
print(correspondence_df)
correspondence_df.to_csv('country_dictionary.csv', index=False)
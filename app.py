import sys
import io
import pycountry
import streamlit as st
from flask import send_file
import pandas as pd
import numpy as np
import os
import re
from docx import Document
from io import BytesIO
from rapidfuzz import process
import streamlit.web.cli as stcli

# Define default file paths
default_vars_file = "vars_fetched.xlsx"
default_pairs_file = "default_pairs.xlsx"
default_dictionary_file = "proper_db.csv"
default_formulas_file = "MK model nov 2023 no form.docx"

def parse_formulas(file):
    doc = Document(file)
    text_data = [p.text for p in doc.paragraphs if p.text.strip() != ""]
    formulas = pd.DataFrame({'text': text_data})
    formulas['text'] = formulas['text'].str.replace('=', '~', regex=False)
    formulas['text'] = formulas['text'].str.replace(' ', '', regex=False)

    def convert_notation(formula, pattern, replace_pattern):
        return re.sub(pattern, replace_pattern, formula)

    # Convert lag, log, and exp notations
    formulas['text'] = formulas['text'].apply(
        lambda x: convert_notation(x, r'(\w+)\(\s*-\s*(\d+)\s*\)', r'lag(\1, \2)'))
    formulas['text'] = formulas['text'].apply(lambda x: convert_notation(x, r'log\((\w+)\)', r'log(\1)'))
    formulas['text'] = formulas['text'].apply(lambda x: convert_notation(x, r'exp\((\w+)\)', r'exp(\1)'))

    # Extract variables
    word_vector = formulas['text'].apply(
        lambda x: re.findall(r'[^]+|\b[a-zA-Z_]+\d*[a-zA-Z_]*|\d+[a-zA-Z_]+\.\d+|[a-zA-Z_]+\.\d+\b', x)).explode()
    word_vector = word_vector.drop_duplicates()

    # Initialize empty lists
    x_vars = []
    lag_vars = []
    log_vars = []
    exp_vars = []

    for var in word_vector:
        var = var.lower()
        if var.startswith('lag'):
            lag_vars.append(var)
        elif var.startswith('log'):
            log_vars.append(var)
        elif var.startswith('exp'):
            exp_vars.append(var)
        else:
            x_vars.append(var)

    # Ensure the same length for all columns
    max_len = max(len(x_vars), len(lag_vars), len(log_vars), len(exp_vars))

    x_vars += [None] * (max_len - len(x_vars))
    lag_vars += [None] * (max_len - len(lag_vars))
    log_vars += [None] * (max_len - len(log_vars))
    exp_vars += [None] * (max_len - len(exp_vars))

    vars_n_DBvars_fetched = pd.DataFrame({
        'variable': x_vars,
        'lag': lag_vars,
        'log': log_vars,
        'exp': exp_vars
    })

    # Clean up variable names
    vars_n_DBvars_fetched['lag'] = vars_n_DBvars_fetched['lag'].str.extract(r'lag\(([^,]+)').fillna('')
    vars_n_DBvars_fetched['log'] = vars_n_DBvars_fetched['log'].str.extract(r'log\(([^)]+)').fillna('')
    vars_n_DBvars_fetched['exp'] = vars_n_DBvars_fetched['exp'].str.extract(r'exp\(([^)]+)').fillna('')

    return vars_n_DBvars_fetched

def read_files(vars_file, pairs_file, dictionary_file):
    vars_n_DBvars_fetched = pd.read_excel(vars_file).sort_values(by="variable")
    dictionary = pd.read_csv(dictionary_file)

    default_pairs = pd.read_excel(default_pairs_file, sheet_name=None)  # Read all sheets


    # Create a combined DataFrame from all sheets in default_pairs
    uservars_defaultvars = pd.DataFrame()
    for sheet_name, df in default_pairs.items():
        if df.shape[1] >= 2:  # Ensure there are at least two columns
            df["variable"] = df["variable"].str.lower()
            df["lid"] = df["lid"].astype(float)
            # df.drop(columns="variable", inplace=True)
            uservars_defaultvars = pd.concat([uservars_defaultvars, df], ignore_index=True)

    # uservars_defaultvars = pd.merge(vars_n_DBvars_fetched, uservars_defaultvars, on="variable", how="left")
    uservars_defaultvars.drop(columns=["excel_eq", "reporter"], inplace=True)

    # Merge with dictionary and handle columns correctly
    data = pd.merge(uservars_defaultvars, dictionary, on="lid", how="left", suffixes=('', '_dict'))
    # Ensure any unwanted columns are dropped
    data.drop(columns=[col for col in data.columns if col.endswith('_dict')], inplace=True)
    data["lid"] = np.nan

    return data, dictionary, country_codes

# Filter DATA based on selected country
def get_country_code(country_name):
    if not country_name:
        return None

    # Get all country names
    country_names = [country.name for country in pycountry.countries]

    # Perform fuzzy matching to find the closest country name
    closest_match, score = process.extractOne(country_name, country_names)

    if score > 80:  # Only consider it a match if the score is sufficiently high
        country = pycountry.countries.get(name=closest_match)
        return country.alpha_2
    else:
        return None


# Extract country codes from sheet names
country_codes = [str(sheet_name) for sheet_name in default_pairs.keys()]
country_codes = sorted(set(country_codes))  # Unique and sorted country codes

# Sidebar for file uploads
st.sidebar.title("Upload Files")
selected_country = st.sidebar.selectbox("Select Country", [""] + country_codes)
uploaded_formulas = st.sidebar.file_uploader("Upload Word File with Formulas", type="docx")
uploaded_vars = st.sidebar.file_uploader("Upload vars_fetched.xlsx", type="xlsx")
uploaded_default_pairs = st.sidebar.file_uploader("Upload default_pairs.xlsx", type="xlsx")
uploaded_dictionary = st.sidebar.file_uploader("Upload proper_db.csv", type="csv")

# Use uploaded formulas file or default
formulas_df = pd.DataFrame()  # Initialize as an empty DataFrame
if uploaded_formulas:
    try:
        formulas_df = parse_formulas(uploaded_formulas)
    except Exception as e:
        st.error(f"Error parsing formulas: {e}")
        st.stop()
elif os.path.exists(default_formulas_file):
    formulas_df = parse_formulas(default_formulas_file)
else:
    st.error("Please upload the Word document with formulas or ensure the default file is available.")
    st.stop()


def save_parsed_formulas_to_xlsx(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

def download_parsed_formulas():
    if not formulas_df.empty:
        output = save_parsed_formulas_to_xlsx(formulas_df)
        st.download_button(
            label="Download Parsed Formulas",
            data=output,
            file_name='vars_fetched.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

# Call the download function in the main part of your Streamlit code
download_parsed_formulas()

def select_file(uploaded_file, default_file):
    # If an uploaded file is provided, use it; otherwise, fall back to the default file
    return uploaded_file if uploaded_file is not None else default_file

# Check if the uploaded files are provided, otherwise use the default files
selected_vars_file = select_file(uploaded_vars, default_vars_file)
selected_pairs_file = select_file(uploaded_default_pairs, default_pairs)
selected_dictionary_file = select_file(uploaded_dictionary, default_dictionary_file)

# Function to check if a file is usable (either uploaded or default)
def is_file_usable(file):
    if isinstance(file, str):  # Check if the file is a default path string
        return os.path.exists(file)
    elif file is not None:  # Check if the file is an uploaded file object
        return True
    return False

# Ensure all necessary files are available
if is_file_usable(selected_vars_file) and is_file_usable(selected_pairs_file) and is_file_usable(selected_dictionary_file):
    # Handle reading the files based on whether they are uploaded or default
    if isinstance(selected_vars_file, str):
        # Use the default file paths
        DATA, dictionary, country_codes = read_files(selected_vars_file, selected_pairs_file, selected_dictionary_file)
    else:
        # Use the uploaded files (remember to handle the file objects correctly)
        DATA, dictionary, country_codes = read_files(selected_vars_file, selected_pairs_file, selected_dictionary_file)
else:
    st.error("Please upload all required files or ensure default files are available in the repository.")
    st.stop()

# Define DATA outside the if statement to ensure it's always defined
DATA = pd.DataFrame()

if selected_country:
    # Convert all country names in DATA["reporter"] to their ISO2 codes
    DATA["reporter"] = DATA["reporter"].apply(get_country_code)

    if selected_country in DATA["reporter"].values:
        # Filter DATA by the selected country code
        DATA = DATA[DATA["reporter"] == selected_country]
    else:
        st.error(f"Country '{selected_country}' not found in the data.")
        st.stop()

# Initialize state
if "states" not in st.session_state:
    st.session_state["states"] = {i: {
        "selected_reporter": DATA["reporter"][i] if i < len(DATA["reporter"]) else "",
        # "selected_indicator": DATA["indicator"][i] if i < len(DATA["indicator"]) else "",
        # "selected_unit": DATA["unit"][i] if i < len(DATA["unit"]) else "",
        "lid": np.nan,
        "blocked": False
    } for i in range(len(DATA))}

# Define functions
def update_state(index, key, value):
    st.session_state["states"][index][key] = value

def render_dropdowns():
    for i in range(len(DATA)):
        variable = DATA["variable"][i]
        state = st.session_state["states"][i]

        col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 1])

        col1.text(variable)
        state["blocked"] = col2.checkbox("block", value=state["blocked"], key=f"block_switch_{i}")

        # Disable dropdowns if blocked
        disabled = state["blocked"]

        filtered_reporters = DATA["reporter"].unique()
        state["selected_reporter"] = col3.selectbox(
            "Reporter",
            options=filtered_reporters,
            index=1 if state["selected_reporter"] in filtered_reporters else 0,
            key=f"reporter_dropdown_{i}",
            disabled=disabled
        )

        filtered_indicators = DATA.loc[
            DATA["reporter"] == state["selected_reporter"], "indicator"
        ].unique()
        state["selected_indicator"] = col4.selectbox(
            "Indicator",
            options=[""] + sorted(filtered_indicators),
            key=f"indicator_dropdown_{i}",
            disabled=disabled
        )

        if not disabled and state["selected_indicator"]:
            state["selected_unit"] = dictionary[
                (dictionary["reporter"] == state["selected_reporter"]) &
                (dictionary["indicator"] == state["selected_indicator"])
            ]["unit"].unique()

            state["selected_unit"] = col5.selectbox(
                "Unit",
                options=[""] + sorted(state["selected_unit"]),
                index=1 if state["selected_unit"] in state["selected_unit"] else 0,
                key=f"unit_dropdown_{i}",
                disabled=disabled
            )

        col6.write(f"LID: {state['lid']}")

# Render dropdowns
render_dropdowns()

# Add save button
if st.button("Save"):
    st.session_state["states"]

# Add download button for DATA
if not DATA.empty:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        DATA.to_excel(writer, index=False, sheet_name='Data')
        workbook = writer.book
        worksheet = writer.sheets['Data']
        worksheet.set_column('A:A', 20)

    output.seek(0)
    st.download_button(
        label="Download DATA.xlsx",
        data=output,
        file_name='DATA.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        key='download_data'
    )


if __name__ == '__main__':
    sys.argv = ["streamlit", "run", "app.py"]
    sys.exit(stcli.main())
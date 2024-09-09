import io
import os
import sys
import streamlit as st
import pandas as pd
import re
from docx import Document
import streamlit.web.cli as stcli

st.set_page_config(layout="wide")


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
    else:
        st.error("No data to download.")


st.sidebar.title("Upload Files")
# selected_country = st.sidebar.selectbox("Select Country", [""] + country_codes)
uploaded_formulas = st.sidebar.file_uploader("Upload Word File with Formulas", type="docx")
uploaded_vars = st.sidebar.file_uploader("Upload vars_fetched.xlsx", type="xlsx")
uploaded_default_pairs = st.sidebar.file_uploader("Upload default_pairs.xlsx", type="xlsx")
uploaded_dictionary = st.sidebar.file_uploader("Upload proper_db.csv", type="csv")

# Use uploaded formulas file or default
formulas_df = pd.DataFrame()  # Initialize as an empty DataFrame
if uploaded_formulas:
    try:
        formulas_df = parse_formulas(uploaded_formulas)
        save_parsed_formulas_to_xlsx(formulas_df)
    except Exception as e:
        st.error(f"Error parsing formulas: {e}")
        st.stop()
elif os.path.exists('MK model nov 2023 no form.docx'):
    formulas_df = parse_formulas('MK model nov 2023 no form.docx')
else:
    st.error("Please upload the Word document with formulas or ensure the default file is available.")
    st.stop()

download_parsed_formulas()

# Load and prepare data
if os.path.exists('vars_fetched.xlsx'):
    vars_n_DBvars_fetched = pd.read_excel("vars_fetched.xlsx")
    if 'Unnamed: 0' in vars_n_DBvars_fetched.columns:
        vars_n_DBvars_fetched = vars_n_DBvars_fetched.drop('Unnamed: 0', axis=1)
    if 'x' in vars_n_DBvars_fetched.columns:
        vars_n_DBvars_fetched['variable'] = vars_n_DBvars_fetched['x']
        vars_n_DBvars_fetched = vars_n_DBvars_fetched.drop('x', axis=1)

dictionary = pd.read_csv("proper_db.csv")
default_pairs = pd.read_excel("default_pairs.xlsx")
default_pairs["variable"] = default_pairs["variable"].str.lower()

uservars_defaultvars = pd.merge(vars_n_DBvars_fetched, default_pairs, on="variable", how="left")
default_data_in = pd.merge(uservars_defaultvars, dictionary, on="lid", how="left")

DATA = default_data_in
DATA['lid'].fillna(0, inplace=True)
DATA['lid'] = DATA['lid'].astype(int)
DATA['excel_eq'].fillna('', inplace=True)

reporter_options = dictionary['reporter'].unique()
indicator_options = dictionary['indicator'].unique()
unit_options = dictionary['unit'].unique()

for i in range(len(DATA)):
    col1, col2, col3, col4, col5, col6 = st.columns([2, 4, 4, 3, 2, 2])

    with col1:
        st.text(DATA.at[i, "variable"])  # Display the 'variable' column as a static text field
    with col2:
        default_reporter_index = list(reporter_options).index(DATA.at[i, 'reporter_y']) if DATA.at[
                                                                                               i, 'reporter_y'] in reporter_options else 0
        col2.selectbox(
            "Reporter",
            options=reporter_options,
            key=f"reporter_dropdown_{i}",
            index=default_reporter_index
        )
    with col3:
        default_indicator_index = list(indicator_options).index(DATA.at[i, 'indicator']) if DATA.at[
                                                                                                i, 'indicator'] in indicator_options else 0
        st.selectbox(
            "Indicator",
            options=indicator_options,
            key=f"indicator_dropdown_{i}",
            index=default_indicator_index
        )
    with col4:
        default_unit_index = list(unit_options).index(DATA.at[i, 'unit']) if DATA.at[i, 'unit'] in unit_options else 0
        col4.selectbox(
            "Unit",
            options=unit_options,
            key=f"unit_dropdown_{i}",
            index=default_unit_index
        )
    with col5:
        st.text(DATA.at[i, "lid"])
    with col6:
        st.text(DATA.at[i, "excel_eq"])

if __name__ == '__main__':
    sys.argv = ["streamlit", "run", "app_r.py"]
    stcli.main()

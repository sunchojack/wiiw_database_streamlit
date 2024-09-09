
import streamlit as st
import pandas as pd
# st.set_page_config(layout="wide")


# core interface goes here:
# main page (streamlit data displayer + dropdowns)
# "choose country" dropdown
# buttons: randomize lids, block variable (user-defined var)
def mainpage():
    def parse_formulas():
        pass  # парсер формул, тупа код. нажал кнопку - едем. генерит файл, дает скачать, вставляет его в сайдбаровские формулы

    def plot_datatable():
        def render_dropdowns():
            pass  # for now

    if st.session_state.get('sidebar_done', False):
        st.text('yay')


def sidepage():
    """
    side page for data upload

    :return:
    """

    with st.sidebar:
        st.header('File uploads')
        # st.subheader(')
        choice_formulas = st.selectbox(label='Formulas', options=['mine', 'default'])
        if choice_formulas == 'mine':
            formulas = st.file_uploader('Upload the docx', type='docx')
            st.session_state['formulas'] = formulas
            st.session_state['formula_parser_needed'] = True
        elif choice_formulas == 'default':
            formulas = pd.read_excel('formulas_mapped.xlsx')
            if 'Unnamed: 0' in formulas.columns:
                formulas.drop('Unnamed: 0', axis=1, inplace=True)
            st.session_state['formulas'] = formulas
            st.session_state['formula_parser_needed'] = False
        else:
            pass

        choice_excel = st.selectbox(label='Mapped Excel Defaults Key', options=['default', 'mine'])
        if choice_excel == 'mine':
            excel_defaults = st.file_uploader('Upload the excel', type='xlsx')
            st.session_state['excel_defaults'] = excel_defaults
        elif choice_excel == 'default':
            excel_defaults = pd.read_excel('excel_defaults_mapped.xlsx')
            st.session_state['excel_defaults'] = excel_defaults
        else:
            pass

        choice_dbkeys = st.selectbox(label='DB Keys', options=['default', 'mine'])
        if choice_dbkeys == 'mine':
            dbkeys = st.file_uploader('Upload db keys', type='csv')
            st.session_state['dbkeys'] = dbkeys
        elif choice_dbkeys == 'default':
            dbkeys = pd.read_csv('database_mapping.csv')
            st.session_state['dbkeys'] = dbkeys
        else:
            pass

    if all(value is not None for value in [st.session_state.get('formulas'), st.session_state.get('excel_defaults'),
                                           st.session_state.get('dbkeys')]):

        if st.sidebar.button('Generate/update'):
            st.write('Formulas Data:')
            formulas = st.session_state['formulas']
            if st.session_state['formula_parser_needed']:
                st.text('ERROR! PARSE YOUR FORMULAS FIRST: <BUTTON>')
            else:
                st.dataframe(formulas)
            st.write('DB Keys Data:')
            st.dataframe(dbkeys)

            st.session_state['sidebar_done'] = True


if __name__ == '__main__':
    sidepage()
    mainpage()
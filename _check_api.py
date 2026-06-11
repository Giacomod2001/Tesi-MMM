import inspect
import streamlit as st

for fn in (st.download_button, st.plotly_chart, st.dataframe, st.data_editor,
           st.progress, st.button, st.container):
    name = getattr(fn, "__name__", str(fn))
    try:
        sig = str(inspect.signature(fn))
    except Exception as e:  # noqa: BLE001
        sig = f"ERR {e}"
    print(name, "::", sig, "\n")

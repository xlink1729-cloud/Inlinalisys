import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Procesador Inclinométrico", layout="wide")
st.title("📊 Análisis de Datos Inclinométricos")

# Panel lateral de configuración
st.sidebar.header("Configuración del Sensor")
constante_k = st.sidebar.number_input(
    "Constante del Sensor (K)", value=20000, step=1000
)
intervalo_l = st.sidebar.number_input(
    "Intervalo del Nodo / Sonda (m)", value=0.5, step=0.1
)

# Carga de archivo CSV
uploaded_file = st.sidebar.file_uploader("Cargar archivo CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("Vista Previa de Datos")
    st.dataframe(df.head())

    # Validación de columnas requeridas
    columnas_req = {"Profundidad", "A0", "A180"}
    if columnas_req.issubset(df.columns):
        # 1. Cálculo del Diferencial (A0 - A180) / 2
        df["Diferencial_A"] = (df["A0"] - df["A180"]) / 2.0

        # 2. Desplazamiento Incremental en mm
        df["Disp_Incremental_mm"] = (
            df["Diferencial_A"] / constante_k
        ) * (intervalo_l * 1000)

        # 3. Desplazamiento Acumulado (desde el fondo hacia la superficie)
        df = df.sort_values(by="Profundidad", ascending=False)
        df["Disp_Acumulado_mm"] = df["Disp_Incremental_mm"].cumsum()

        # 4. Checksum
        df["Checksum"] = df["A0"] + df["A180"]

        # Gráficas
        col1, col2 = st.columns([2, 1])

        with col1:
            fig = px.line(
                df,
                x="Disp_Acumulado_mm",
                y="Profundidad",
                title="Perfil de Desplazamiento Acumulado (Eje A)",
                labels={
                    "Disp_Acumulado_mm": "Desplazamiento Acumulado (mm)",
                    "Profundidad": "Profundidad (m)",
                },
                markers=True,
            )
            fig.update_yaxes(
                autorange="reversed"
            )  # Invertir eje Y para representar profundidad
            fig.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Verificación (Checksum)")
            st.dataframe(
                df[["Profundidad", "Checksum", "Disp_Acumulado_mm"]].reset_index(
                    drop=True
                )
            )
    else:
        st.error(f"El archivo debe contener las columnas: {columnas_req}")
else:
    st.info("👈 Carga un archivo CSV en el panel lateral para iniciar el análisis.")
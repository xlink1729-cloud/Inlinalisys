import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Sistema de Análisis Inclinométrico", layout="wide"
)
st.title("📊 Análisis de Deformación Inclinométrica")

# ---------------------------------------------------------
# 1. METADATOS DEL POZO Y CONFIGURACIÓN (Panel Lateral)
# ---------------------------------------------------------
st.sidebar.header("📍 Metadatos del Pozo")
nombre_pozo = st.sidebar.text_input("Identificador del Pozo", value="PZ-01")
profundidad_total = st.sidebar.number_input(
    "Profundidad Total del Pozo (m)", value=30.0, step=0.5
)
azimut_eje_a = st.sidebar.number_input(
    "Azimut Eje A+ (°)", value=45.0, min_value=0.0, max_value=360.0
)

# Coordenadas geográficas
st.sidebar.subheader("Coordenadas Geográficas")
latitud = st.sidebar.number_input(
    "Latitud", value=25.6866, format="%.6f"
)  # Ejemplo
longitud = st.sidebar.number_input(
    "Longitud", value=-100.3161, format="%.6f"
)

st.sidebar.header("⚙️ Configuración del Sensor")
constante_k = st.sidebar.number_input(
    "Constante del Sensor (K)", value=20000, step=1000
)
intervalo_l = st.sidebar.number_input(
    "Intervalo entre Nodos (m)", value=0.5, step=0.1
)

# Carga de archivo CSV
uploaded_file = st.sidebar.file_uploader("Cargar archivo CSV", type=["csv"])

# ---------------------------------------------------------
# 2. DESPLIEGUE DE METADATOS EN EL ENCABEZADO
# ---------------------------------------------------------
col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
col_meta1.metric("Pozo Monitoreado", nombre_pozo)
col_meta2.metric("Profundidad Registrada", f"{profundidad_total} m")
col_meta3.metric("Orientación Eje A+", f"{azimut_eje_a}°")
col_meta4.metric("Coordenadas", f"{latitud:.4f}, {longitud:.4f}")

st.markdown("---")

# ---------------------------------------------------------
# 3. PROCESAMIENTO Y VISUALIZACIÓN
# ---------------------------------------------------------
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("Vista Previa de Datos Cargados")
    st.dataframe(df.head(), use_container_width=True)

    columnas_req = {"Profundidad", "A0", "A180"}
    if columnas_req.issubset(df.columns):
        # Cálculos Eje A
        df["Diferencial_A"] = (df["A0"] - df["A180"]) / 2.0
        df["Disp_Incremental_mm"] = (
            df["Diferencial_A"] / constante_k
        ) * (intervalo_l * 1000)

        # Ordenar desde el fondo hacia la superficie
        df = df.sort_values(by="Profundidad", ascending=False)
        df["Disp_Acumulado_mm"] = df["Disp_Incremental_mm"].cumsum()
        df["Checksum"] = df["A0"] + df["A180"]

        # Gráfica de Perfil de Desplazamiento y Mapa
        tab1, tab2 = st.tabs(
            ["📉 Perfil de Desplazamiento", "🗺️ Ubicación del Pozo"]
        )

        with tab1:
            fig = px.line(
                df,
                x="Disp_Acumulado_mm",
                y="Profundidad",
                title=f"Perfil de Desplazamiento Acumulado - Pozo: {nombre_pozo}",
                labels={
                    "Disp_Acumulado_mm": "Desplazamiento Acumulado (mm)",
                    "Profundidad": "Profundidad (m)",
                },
                markers=True,
            )
            fig.update_yaxes(autorange="reversed")
            fig.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.write(
                f"**Ubicación del Pozo {nombre_pozo} en coordenadas GPS:**"
            )
            df_mapa = pd.DataFrame({"lat": [latitud], "lon": [longitud]})
            st.map(df_mapa, zoom=14)

    else:
        st.error(
            f"El archivo CSV debe contener al menos las columnas: {columnas_req}"
        )
else:
    st.info(
        "👈 Ingrese los metadatos en el panel izquierdo y cargue el archivo CSV para visualizar el análisis."
    )

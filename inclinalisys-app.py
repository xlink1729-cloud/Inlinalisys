import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - Análisis Inclinométrico", layout="wide"
)
st.title("📊 Procesador de Inclinómetro In-Situ (RST IPI)")

# ---------------------------------------------------------
# 1. METADATOS EXTRAÍDOS DEL REPORTE DE CAMPO
# ---------------------------------------------------------
st.sidebar.header("📍 Parámetros del Pozo (Ficha Técnica)")
nombre_pozo = st.sidebar.text_input("Identificador del Pozo", value="PROYECTO")
profundidad_instalacion = st.sidebar.number_input(
    "Prof. Instalación (m)", value=23.77, format="%.2f"
)
no_sensores = st.sidebar.number_input("No. de Sensores / Nodos", value=12)
azimut_eje_a = st.sidebar.number_input("Azimuth Eje A+ (°)", value=5.32)

st.sidebar.subheader("Coordenadas UTM (WGS84)")
utm_x = st.sidebar.number_input("Coordenada X (Easting)", value=651132.69)
utm_y = st.sidebar.number_input("Coordenada Y (Northing)", value=2127107.11)
elevacion_z = st.sidebar.number_input("Elevación Z (msnm)", value=610.19)

st.sidebar.header("⚙️ Modelo de Sensor")
marca_modelo = st.sidebar.text_input("Modelo", value="RST IPI27050-70MM")
constante_k = st.sidebar.number_input(
    "Constante K (RST)", value=20000, step=1000
)

# Cálculo automático de intervalo entre nodos
intervalo_l = profundidad_instalacion / no_sensores if no_sensores > 0 else 0.5
st.sidebar.info(f"📏 Intervalo calculado entre nodos: **{intervalo_l:.2f} m**")

# Carga de archivo CSV
uploaded_file = st.sidebar.file_uploader("Cargar archivo CSV", type=["csv"])

# ---------------------------------------------------------
# 2. TARJETAS DE INFORMACIÓN TÉCNICA
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pozo", nombre_pozo)
col2.metric("Profundidad", f"{profundidad_instalacion} m")
col3.metric("Sensores RST", f"{no_sensores} Nodos")
col4.metric("Azimuth A+", f"{azimut_eje_a}°")
col5.metric("Elevación (Z)", f"{elevacion_z} msnm")

st.markdown("---")

# ---------------------------------------------------------
# 3. PROCESAMIENTO Y GRÁFICAS
# ---------------------------------------------------------
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("Vista Previa de Datos del Inclinómetro")
    st.dataframe(df.head(12), use_container_width=True)

    # Validar que el archivo contenga los 12 sensores
    if len(df) != no_sensores:
        st.warning(
            f"⚠️ Atención: El archivo contiene {len(df)} registros, pero la ficha indica {no_sensores} sensores."
        )

    columnas_req = {"Profundidad", "A0", "A180"}
    if columnas_req.issubset(df.columns):
        # 1. Cálculo del Diferencial (A0 - A180) / 2
        df["Diferencial_A"] = (df["A0"] - df["A180"]) / 2.0

        # 2. Desplazamiento Incremental en mm usando el intervalo real (1.98 m)
        df["Disp_Incremental_mm"] = (
            df["Diferencial_A"] / constante_k
        ) * (intervalo_l * 1000)

        # 3. Desplazamiento Acumulado ordenado desde el fondo
        df = df.sort_values(by="Profundidad", ascending=False)
        df["Disp_Acumulado_mm"] = df["Disp_Incremental_mm"].cumsum()
        df["Checksum"] = df["A0"] + df["A180"]

        # Gráfica interactiva de deformación vs profundidad
        fig = px.line(
            df,
            x="Disp_Acumulado_mm",
            y="Profundidad",
            title=f"Perfil de Deformación Acumulada - Inclinómetro RST ({nombre_pozo})",
            labels={
                "Disp_Acumulado_mm": "Desplazamiento Acumulado (mm)",
                "Profundidad": "Profundidad (m)",
            },
            markers=True,
        )
        fig.update_yaxes(
            autorange="reversed", range=[profundidad_instalacion, 0]
        )
        fig.add_vline(
            x=0, line_dash="dash", line_color="red", annotation_text="Línea Base (0 mm)"
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(
            f"El archivo debe tener las columnas básicas: {columnas_req}"
        )
else:
    st.info("👈 Carga el archivo CSV con las lecturas de los 12 sensores para ver el perfil.")

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - Análisis Inclinométrico DT2485", layout="wide"
)
st.title("📊 Procesador de Inclinómetro In-Situ (Datalogger DT2485)")

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

st.sidebar.header("⚙️ Modelo de Datalogger")
marca_modelo = st.sidebar.text_input("Modelo", value="DT2485 IPI Logger")

# Cálculo automático de intervalo entre nodos (Ej. 23.77m / 12 nodos = ~1.98 m por tramo)
intervalo_l = (
    profundidad_instalacion / no_sensores if no_sensores > 0 else 1.98
)
st.sidebar.info(f"📏 Tramo entre nodos: **{intervalo_l:.2f} m**")

# Carga del archivo CSV exportado del DT2485
uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo CSV (DT2485)", type=["csv"]
)

# ---------------------------------------------------------
# 2. TARJETAS DE INFORMACIÓN TÉCNICA
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pozo", nombre_pozo)
col2.metric("Profundidad", f"{profundidad_instalacion} m")
col3.metric("Sensores IPI", f"{no_sensores} Nodos")
col4.metric("Azimuth A+", f"{azimut_eje_a}°")
col5.metric("Elevación (Z)", f"{elevacion_z} msnm")

st.markdown("---")

# ---------------------------------------------------------
# 3. PROCESAMIENTO DE REGISTROS DT2485 Y GRÁFICA
# ---------------------------------------------------------
if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    st.subheader("Vista Previa del Registro del DT2485")
    st.dataframe(df_raw.head(5), use_container_width=True)

    # Identificar columnas del DT2485
    col_axis_a = [c for c in df_raw.columns if c.startswith("Axis A")]

    if col_axis_a and "TIMESTAMP" in df_raw.columns:
        # Selector para explorar cualquier registro guardado en el DT2485
        timestamps = df_raw["TIMESTAMP"].dropna().unique()
        fecha_sel = st.selectbox(
            "🕒 Selecciona la Lectura / Timestamp a Graficar:",
            timestamps,
            index=len(timestamps) - 1,  # Por defecto toma la más reciente
        )

        # Extraer la fila de medición seleccionada
        fila = df_raw[df_raw["TIMESTAMP"] == fecha_sel].iloc[0]

        # Mapeo de datos por sensor
        datos_sensores = []
        for i in range(1, int(no_sensores) + 1):
            col_a = f"Axis A {i}"
            val_sin_a = fila.get(col_a, np.nan)

            # Filtrar códigos de desconexión/error del DT2485 (ej. 0.999998)
            if pd.notnull(val_sin_a) and abs(val_sin_a) > 0.5:
                val_sin_a = np.nan

            prof = i * intervalo_l
            # Desplazamiento incremental en mm = sin(theta) * L_tramo (mm)
            disp_inc = (
                val_sin_a * (intervalo_l * 1000)
                if pd.notnull(val_sin_a)
                else 0.0
            )

            datos_sensores.append(
                {
                    "Nodo": f"Nodo {i}",
                    "Profundidad": prof,
                    "Sin_A": val_sin_a,
                    "Disp_Incremental_mm": disp_inc,
                }
            )

        df = pd.DataFrame(datos_sensores)

        # Integración acumulada desde la base del pozo hacia la superficie
        df = df.sort_values(by="Profundidad", ascending=False)
        df["Disp_Acumulado_mm"] = df["Disp_Incremental_mm"].cumsum()

        # Reordenar de la superficie hacia el fondo para graficar
        df = df.sort_values(by="Profundidad", ascending=True)

        # Gráfica interactiva de deformación acumulada
        fig = px.line(
            df,
            x="Disp_Acumulado_mm",
            y="Profundidad",
            title=f"Perfil de Deformación Acumulada (Eje A) - DT2485 [{fecha_sel}]",
            labels={
                "Disp_Acumulado_mm": "Desplazamiento Acumulado (mm)",
                "Profundidad": "Profundidad (m)",
            },
            markers=True,
            text="Nodo",
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
            "El archivo cargado no coincide con el formato del logger DT2485 ('TIMESTAMP', 'Axis A 1', ...)."
        )
else:
    st.info(
        "👈 Carga el archivo CSV del datalogger DT2485 para visualizar el perfil."
    )

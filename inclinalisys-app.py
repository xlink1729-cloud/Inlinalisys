import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - IncliAnalysis", layout="wide"
)
st.title("📊 Procesador Inclinométrico In-Situ (IncliAnalysis Suite)")

# ---------------------------------------------------------
# 1. PARÁMETROS DEL POZO Y FICHA TÉCNICA
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

intervalo_l = (
    profundidad_instalacion / no_sensores if no_sensores > 0 else 1.98
)
st.sidebar.info(f"📏 Tramo entre nodos: **{intervalo_l:.2f} m**")

uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo CSV (DT2485)", type=["csv"]
)

# ---------------------------------------------------------
# 2. MÉTRICAS PRINCIPALES
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pozo", nombre_pozo)
col2.metric("Profundidad", f"{profundidad_instalacion} m")
col3.metric("Sensores IPI", f"{no_sensores} Nodos")
col4.metric("Azimuth A+", f"{azimut_eje_a}°")
col5.metric("Elevación (Z)", f"{elevacion_z} msnm")

st.markdown("---")

# ---------------------------------------------------------
# 3. MÓDULO DE ANÁLISIS INCLIANALYSIS Y TABLA DE DATOS
# ---------------------------------------------------------
if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    # Identificar columnas del DT2485
    col_axis_a = [c for c in df_raw.columns if c.startswith("Axis A")]

    if col_axis_a and "TIMESTAMP" in df_raw.columns:
        # Selector de Fecha
        timestamps = df_raw["TIMESTAMP"].dropna().unique()
        fecha_sel = st.selectbox(
            "🕒 Selecciona Fecha/Hora para Perfil:",
            timestamps,
            index=len(timestamps) - 1,
        )

        # Extraer fila seleccionada
        fila = df_raw[df_raw["TIMESTAMP"] == fecha_sel].iloc[0]

        # Construir datos por sensor para esa fecha
        datos_sensores = []
        for i in range(1, int(no_sensores) + 1):
            col_a = f"Axis A {i}"
            col_b = f"Axis B {i}"

            val_sin_a = fila.get(col_a, np.nan)
            val_sin_b = fila.get(col_b, np.nan)

            # Filtrar errores (ej. 0.999998)
            if pd.notnull(val_sin_a) and abs(val_sin_a) > 0.5:
                val_sin_a = np.nan
            if pd.notnull(val_sin_b) and abs(val_sin_b) > 0.5:
                val_sin_b = np.nan

            prof = i * intervalo_l
            disp_inc_a = (
                val_sin_a * (intervalo_l * 1000)
                if pd.notnull(val_sin_a)
                else 0.0
            )
            disp_inc_b = (
                val_sin_b * (intervalo_l * 1000)
                if pd.notnull(val_sin_b)
                else 0.0
            )

            datos_sensores.append(
                {
                    "Nodo": f"Nodo {i}",
                    "Profundidad (m)": prof,
                    "Sin_A": val_sin_a,
                    "Sin_B": val_sin_b,
                    "Disp_Inc_A (mm)": disp_inc_a,
                    "Disp_Inc_B (mm)": disp_inc_b,
                }
            )

        df = pd.DataFrame(datos_sensores)

        # Cálculos de Desplazamiento Acumulado desde el fondo hacia la superficie
        df = df.sort_values(by="Profundidad (m)", ascending=False)
        df["Disp_Acum_A (mm)"] = df["Disp_Inc_A (mm)"].cumsum()
        df["Disp_Acum_B (mm)"] = df["Disp_Inc_B (mm)"].cumsum()
        # Magnitud vectorial combinada (A y B)
        df["Vector_Resultante (mm)"] = np.sqrt(
            df["Disp_Acum_A (mm)"] ** 2 + df["Disp_Acum_B (mm)"] ** 2
        )
        df = df.sort_values(by="Profundidad (m)", ascending=True)

        # ---------------------------------------------------------
        # BARRA DE PESTAÑAS (INCLIANALYSIS TOOLBAR)
        # ---------------------------------------------------------
        tab_cum, tab_inc, tab_abs, tab_time, tab_vector, tab_polar = st.tabs([
            "📊 Cumulative",
            "📉 Incremental",
            "📐 Absolute",
            "📈 Time Plot",
            "🧭 Vector Plot",
            "🎯 Polar Plot",
        ])

        # 1. CUMULATIVE PLOT
        with tab_cum:
            fig_cum = px.line(
                df,
                x="Disp_Acum_A (mm)",
                y="Profundidad (m)",
                title=f"Cumulative Displacement (Desplazamiento Acumulado) - Eje A [{fecha_sel}]",
                labels={
                    "Disp_Acum_A (mm)": "Desplazamiento Acumulado (mm)",
                    "Profundidad (m)": "Profundidad (m)",
                },
                markers=True,
                text="Nodo",
            )
            fig_cum.update_yaxes(
                autorange="reversed", range=[profundidad_instalacion, 0]
            )
            fig_cum.add_vline(x=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig_cum, use_container_width=True)

        # 2. INCREMENTAL PLOT
        with tab_inc:
            fig_inc = px.bar(
                df,
                x="Disp_Inc_A (mm)",
                y="Profundidad (m)",
                orientation="h",
                title=f"Incremental Movement (Movimiento por Tramo) - Eje A [{fecha_sel}]",
                labels={
                    "Disp_Inc_A (mm)": "Movimiento Incremental (mm)",
                    "Profundidad (m)": "Profundidad (m)",
                },
                text_auto=True,
            )
            fig_inc.update_yaxes(
                autorange="reversed", range=[profundidad_instalacion, 0]
            )
            st.plotly_chart(fig_inc, use_container_width=True)

        # 3. ABSOLUTE PLOT (ÁNGULO / DEFORMACIÓN ABSOLUTA)
        with tab_abs:
            fig_abs = px.line(
                df,
                x="Sin_A",
                y="Profundidad (m)",
                title=f"Absolute Position / Inclinación Absoluta [sin(θ)] [{fecha_sel}]",
                labels={
                    "Sin_A": "Seno del Ángulo sin(θ)",
                    "Profundidad (m)": "Profundidad (m)",
                },
                markers=True,
            )
            fig_abs.update_yaxes(
                autorange="reversed", range=[profundidad_instalacion, 0]
            )
            st.plotly_chart(fig_abs, use_container_width=True)

        # 4. TIME PLOT (EVOLUCIÓN EN EL TIEMPO PARA UN NODO)
        with tab_time:
            nodo_sel = st.selectbox(
                "Selecciona el Nodo/Sensor a evaluar en el tiempo:",
                [f"Axis A {i}" for i in range(1, int(no_sensores) + 1)],
            )
            fig_time = px.line(
                df_raw,
                x="TIMESTAMP",
                y=nodo_sel,
                title=f"Time Plot - Evolución Temporal en {nodo_sel}",
                labels={"TIMESTAMP": "Fecha / Hora", nodo_sel: "sin(θ)"},
            )
            st.plotly_chart(fig_time, use_container_width=True)

        # 5. VECTOR PLOT (MAGNITUD DE MOVIMIENTO COMBINADO)
        with tab_vector:
            fig_vec = px.line(
                df,
                x="Vector_Resultante (mm)",
                y="Profundidad (m)",
                title=f"Vector Resultante de Desplazamiento (A + B) [{fecha_sel}]",
                labels={
                    "Vector_Resultante (mm)": "Magnitud Resultante (mm)",
                    "Profundidad (m)": "Profundidad (m)",
                },
                markers=True,
            )
            fig_vec.update_yaxes(
                autorange="reversed", range=[profundidad_instalacion, 0]
            )
            st.plotly_chart(fig_vec, use_container_width=True)

        # 6. POLAR PLOT (DIRECCIÓN 2D DEL MOVIMIENTO)
        with tab_polar:
            fig_polar = px.scatter(
                df,
                x="Disp_Acum_A (mm)",
                y="Disp_Acum_B (mm)",
                color="Nodo",
                text="Nodo",
                title=f"Polar / Plan View Movement (Plano Vista Superior A vs B) [{fecha_sel}]",
                labels={
                    "Disp_Acum_A (mm)": "Eje A (mm)",
                    "Disp_Acum_B (mm)": "Eje B (mm)",
                },
            )
            fig_polar.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_polar.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_polar, use_container_width=True)

        # ---------------------------------------------------------
        # 4. TABLA DE RESULTADOS PROCESADOS (RESTAURADA)
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader(f"📋 Tabla de Datos Procesados — Registro: {fecha_sel}")
        st.dataframe(df, use_container_width=True)

    else:
        st.error("El archivo no tiene el formato DT2485 esperado.")
else:
    st.info("👈 Carga el archivo CSV del DT2485 para habilitar la suite IncliAnalysis.")

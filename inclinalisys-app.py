import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - IncliAnalysis DT2485", layout="wide"
)
st.title("📊 Procesador Inclinométrico In-Situ (Datalogger DT2485)")

# ---------------------------------------------------------
# 1. PARÁMETROS DEL POZO Y FICHA TÉCNICA
# ---------------------------------------------------------
st.sidebar.header("📍 Parámetros del Pozo")
nombre_pozo = st.sidebar.text_input("Identificador del Pozo", value="PROYECTO")
profundidad_instalacion = st.sidebar.number_input(
    "Prof. Instalación (m)", value=23.77, format="%.2f"
)
no_sensores = st.sidebar.number_input("No. de Sensores / Nodos", value=12)
azimut_eje_a = st.sidebar.number_input("Azimuth Eje A+ (°)", value=5.32)

intervalo_l = (
    profundidad_instalacion / no_sensores if no_sensores > 0 else 1.98
)
st.sidebar.info(f"📏 Tramo por sensor: **{intervalo_l:.2f} m**")

uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo CSV (DT2485)", type=["csv"]
)

# ---------------------------------------------------------
# 2. PROCESAMIENTO CORRECTO DE ACUMULACIÓN DESDE EL FONDO
# ---------------------------------------------------------
if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    col_axis_a = [c for c in df_raw.columns if c.startswith("Axis A")]

    if col_axis_a and "TIMESTAMP" in df_raw.columns:
        timestamps = df_raw["TIMESTAMP"].dropna().unique()

        col_fecha1, col_fecha2 = st.columns(2)

        with col_fecha1:
            fecha_base = st.selectbox(
                "🟢 Selecciona Lectura BASE:", timestamps, index=0
            )

        with col_fecha2:
            fecha_sel = st.selectbox(
                "🔴 Selecciona Lectura ACTUAL:",
                timestamps,
                index=len(timestamps) - 1,
            )

        fila_base = df_raw[df_raw["TIMESTAMP"] == fecha_base].iloc[0]
        fila_actual = df_raw[df_raw["TIMESTAMP"] == fecha_sel].iloc[0]

        # 1. Recolectamos los deltas por sensor del 1 al 12
        nodos_lista = []
        profundidades = []
        disp_inc_a_list = []
        disp_inc_b_list = []

        for i in range(1, int(no_sensores) + 1):
            col_a = f"Axis A {i}"
            col_b = f"Axis B {i}"

            raw_base_a = fila_base.get(col_a, np.nan)
            raw_act_a = fila_actual.get(col_a, np.nan)

            raw_base_b = fila_base.get(col_b, np.nan)
            raw_act_b = fila_actual.get(col_b, np.nan)

            # Filtrar errores (0.999998)
            if (
                pd.notnull(raw_act_a)
                and abs(raw_act_a) > 0.5
                or (pd.notnull(raw_base_a) and abs(raw_base_a) > 0.5)
            ):
                d_sin_a = 0.0
            else:
                d_sin_a = (
                    raw_act_a - raw_base_a
                    if pd.notnull(raw_act_a) and pd.notnull(raw_base_a)
                    else 0.0
                )

            if (
                pd.notnull(raw_act_b)
                and abs(raw_act_b) > 0.5
                or (pd.notnull(raw_base_b) and abs(raw_base_b) > 0.5)
            ):
                d_sin_b = 0.0
            else:
                d_sin_b = (
                    raw_act_b - raw_base_b
                    if pd.notnull(raw_act_b) and pd.notnull(raw_base_b)
                    else 0.0
                )

            # Profundidad desde la superficie (Nodo 1 = ~1.98m, Nodo 12 = 23.77m)
            prof = i * intervalo_l

            nodos_lista.append(f"Nodo {i}")
            profundidades.append(prof)
            disp_inc_a_list.append(d_sin_a * (intervalo_l * 1000))
            disp_inc_b_list.append(d_sin_b * (intervalo_l * 1000))

        # 2. INVERSIÓN FÍSICA: Para acumular desde la base fija (Nodo 12 -> Nodo 1)
        # Invertimos las listas de abajo hacia arriba
        inc_a_rev = disp_inc_a_list[::-1]
        inc_b_rev = disp_inc_b_list[::-1]

        # Hacemos la suma acumulada partiendo desde el fondo (Nodo 12 = 0 mm)
        acum_a_rev = np.cumsum(inc_a_rev) - inc_a_rev[0]
        acum_b_rev = np.cumsum(inc_b_rev) - inc_b_rev[0]

        # Revertimos de nuevo el resultado para que coincida con la lista del Nodo 1 al 12
        disp_acum_a = acum_a_rev[::-1]
        disp_acum_b = acum_b_rev[::-1]
        vector_resultante = np.sqrt(disp_acum_a**2 + disp_acum_b**2)

        # 3. Crear DataFrame Final Ordenado
        df = pd.DataFrame({
            "Nodo": nodos_lista,
            "Profundidad (m)": profundidades,
            "Disp_Inc_A (mm)": disp_inc_a_list,
            "Disp_Acum_A (mm)": disp_acum_a,
            "Disp_Inc_B (mm)": disp_inc_b_list,
            "Disp_Acum_B (mm)": disp_acum_b,
            "Vector_Resultante (mm)": vector_resultante,
        })

        # ---------------------------------------------------------
        # PESTAÑAS DE ANÁLISIS
        # ---------------------------------------------------------
        tab_cum, tab_inc, tab_time, tab_polar = st.tabs([
            "📊 Cumulative",
            "📉 Incremental",
            "📈 Time Plot",
            "🎯 Polar Plot",
        ])

        # 1. CUMULATIVE PLOT (PERFIL CONTINUO DESDE BASE EN 0 mm)
        with tab_cum:
            fig_cum = go.Figure()

            # Eje A
            fig_cum.add_trace(
                go.Scatter(
                    x=df["Disp_Acum_A (mm)"],
                    y=df["Profundidad (m)"],
                    mode="lines+markers",
                    name="Eje A (mm)",
                    line=dict(color="blue", width=2),
                    marker=dict(symbol="circle", size=8),
                    text=df["Nodo"],
                )
            )

            # Eje B
            fig_cum.add_trace(
                go.Scatter(
                    x=df["Disp_Acum_B (mm)"],
                    y=df["Profundidad (m)"],
                    mode="lines+markers",
                    name="Eje B (mm)",
                    line=dict(color="green", width=2),
                    marker=dict(symbol="square", size=8),
                    text=df["Nodo"],
                )
            )

            # Resultante
            fig_cum.add_trace(
                go.Scatter(
                    x=df["Vector_Resultante (mm)"],
                    y=df["Profundidad (m)"],
                    mode="lines+markers",
                    name="Resultante (mm)",
                    line=dict(color="red", width=2, dash="dash"),
                    marker=dict(symbol="triangle-up", size=8),
                    text=df["Nodo"],
                )
            )

            fig_cum.update_layout(
                title=f"Perfil de Desplazamiento Acumulado ({fecha_base} al {fecha_sel})",
                xaxis_title="Desplazamiento Acumulado (mm)",
                yaxis_title="Profundidad (m)",
                yaxis=dict(autorange="reversed"),
                template="plotly_white",
            )
            fig_cum.add_vline(x=0, line_dash="dot", line_color="gray")
            st.plotly_chart(fig_cum, use_container_width=True)

        # 2. INCREMENTAL
        with tab_inc:
            fig_inc = go.Figure()
            fig_inc.add_trace(
                go.Bar(
                    x=df["Disp_Inc_A (mm)"],
                    y=df["Profundidad (m)"],
                    orientation="h",
                    name="Eje A",
                )
            )
            fig_inc.update_layout(
                title="Movimiento Incremental por Tramo (Eje A)",
                xaxis_title="Desplazamiento Incremental (mm)",
                yaxis_title="Profundidad (m)",
                yaxis=dict(autorange="reversed"),
                template="plotly_white",
            )
            st.plotly_chart(fig_inc, use_container_width=True)

        # 3. TIME PLOT
        with tab_time:
            nodo_sel = st.selectbox(
                "Selecciona el Nodo a evaluar en el tiempo:",
                [f"Axis A {i}" for i in range(1, int(no_sensores) + 1)],
            )
            fig_time = go.Figure()
            fig_time.add_trace(
                go.Scatter(
                    x=df_raw["TIMESTAMP"],
                    y=df_raw[nodo_sel],
                    mode="lines",
                    name=nodo_sel,
                )
            )
            fig_time.update_layout(
                title=f"Evolución Temporal del Sensor {nodo_sel}",
                xaxis_title="Fecha / Hora",
                yaxis_title="sin(θ)",
                template="plotly_white",
            )
            st.plotly_chart(fig_time, use_container_width=True)

        # 4. POLAR PLOT
        with tab_polar:
            fig_polar = go.Figure()
            fig_polar.add_trace(
                go.Scatter(
                    x=df["Disp_Acum_A (mm)"],
                    y=df["Disp_Acum_B (mm)"],
                    mode="markers+text",
                    text=df["Nodo"],
                    textposition="top center",
                    marker=dict(size=10, color=df["Profundidad (m)"]),
                )
            )
            fig_polar.update_layout(
                title="Vista en Planta (Plano A vs B)",
                xaxis_title="Desplazamiento Eje A (mm)",
                yaxis_title="Desplazamiento Eje B (mm)",
                template="plotly_white",
            )
            fig_polar.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_polar.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_polar, use_container_width=True)

        # ---------------------------------------------------------
        # TABLA DE RESULTADOS
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("📋 Tabla de Desplazamientos Procesados")
        st.dataframe(df, use_container_width=True)

    else:
        st.error("El archivo no tiene las columnas del DT2485.")

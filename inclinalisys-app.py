import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - IncliAnalysis Suite", layout="wide"
)
st.title("📊 Procesador Inclinométrico In-Situ (IncliAnalysis Suite)")

# ---------------------------------------------------------
# 1. PARÁMETROS DEL POZO Y FICHA TÉCNICA
# ---------------------------------------------------------
st.sidebar.header("📍 Parámetros del Pozo (Ficha Técnica)")
nombre_pozo = st.sidebar.text_input("Identificador del Pozo", value="PROYECTO")
profundidad_instalacion = st.sidebar.number_input(
    "Prof. Instalación Total (m)", value=23.77, format="%.2f"
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

# ---------------------------------------------------------
# FILTRO DE PROFUNDIDAD Y LIMPIEZA
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("🎯 Filtro de Profundidad")
profundidad_max_evaluar = st.sidebar.slider(
    "Evaluar hasta profundidad (m):",
    min_value=float(intervalo_l),
    max_value=float(profundidad_instalacion),
    value=float(profundidad_instalacion),
    step=float(intervalo_l),
)

uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo CSV (DT2485)", type=["csv"]
)

# ---------------------------------------------------------
# 2. MÉTRICAS PRINCIPALES Y DEPURACIÓN AUTOMÁTICA
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pozo", nombre_pozo)
col2.metric("Prof. Evaluar", f"{profundidad_max_evaluar:.2f} m")
col3.metric("Sensores IPI", f"{no_sensores} Nodos")
col4.metric("Azimuth A+", f"{azimut_eje_a}°")
col5.metric("Elevación (Z)", f"{elevacion_z} msnm")

st.markdown("---")

# ---------------------------------------------------------
# 3. MÓDULO DE DEPURACIÓN Y ANÁLISIS
# ---------------------------------------------------------
if uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)

    # Identificar columnas de los sensores (Axis A y Axis B)
    cols_sensores = [
        c
        for c in df_raw.columns
        if c.startswith("Axis A") or c.startswith("Axis B")
    ]

    if cols_sensores and "TIMESTAMP" in df_raw.columns:
        # ---------------------------------------------------------
        # FILTRADO Y LIMPIEZA AUTOMÁTICA AL CARGAR
        # ---------------------------------------------------------
        df_clean = df_raw.copy()

        # Reemplazar códigos de error típicos (0.999998, -0.999998 o valores desmedidos fuera de [-0.5, 0.5]) por NaN
        num_errores_detectados = 0
        for col in cols_sensores:
            # Convertir a numérico por seguridad
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

            # Máscara de detección de errores
            mask_error = (
                (df_clean[col].isna())
                | (df_clean[col].abs() > 0.5)
                | (df_clean[col].round(4) == 0.9999)
            )

            num_errores_detectados += mask_error.sum()
            df_clean.loc[mask_error, col] = np.nan

        # Notificación del filtrado en la interfaz
        if num_errores_detectados > 0:
            st.warning(
                f"🧹 **Filtro de Limpieza Activado:** Se detectaron y descartaron **{num_errores_detectados} lecturas de error o fuera de rango (ej. 0.999998)** del archivo."
            )
        else:
            st.success(
                "✅ **Calidad de Datos:** El archivo cargado no presenta códigos de error o registros fuera de rango."
            )

        timestamps = df_clean["TIMESTAMP"].dropna().unique()

        col_fecha1, col_fecha2 = st.columns(2)

        with col_fecha1:
            fecha_base = st.selectbox(
                "🟢 Selecciona la Lectura BASE (Inicial / Zero Reading):",
                timestamps,
                index=0,
            )

        with col_fecha2:
            fecha_sel = st.selectbox(
                "🔴 Selecciona la Lectura ACTUAL a Evaluar:",
                timestamps,
                index=len(timestamps) - 1,
            )

        fila_base = df_clean[df_clean["TIMESTAMP"] == fecha_base].iloc[0]
        fila_actual = df_clean[df_clean["TIMESTAMP"] == fecha_sel].iloc[0]

        # Recolección de Deltas con datos limpios
        nodos_lista = []
        profundidades = []
        disp_inc_a_list = []
        disp_inc_b_list = []
        sin_a_act = []
        sin_b_act = []

        for i in range(1, int(no_sensores) + 1):
            prof = i * intervalo_l

            if prof <= profundidad_max_evaluar + 0.01:
                col_a = f"Axis A {i}"
                col_b = f"Axis B {i}"

                raw_base_a = fila_base.get(col_a, np.nan)
                raw_act_a = fila_actual.get(col_a, np.nan)

                raw_base_b = fila_base.get(col_b, np.nan)
                raw_act_b = fila_actual.get(col_b, np.nan)

                # Calcular delta si ambas lecturas son numéricas válidas
                if pd.notnull(raw_act_a) and pd.notnull(raw_base_a):
                    v_a = raw_act_a
                    d_sin_a = raw_act_a - raw_base_a
                else:
                    v_a = np.nan
                    d_sin_a = 0.0

                if pd.notnull(raw_act_b) and pd.notnull(raw_base_b):
                    v_b = raw_act_b
                    d_sin_b = raw_act_b - raw_base_b
                else:
                    v_b = np.nan
                    d_sin_b = 0.0

                nodos_lista.append(f"Nodo {i}")
                profundidades.append(prof)
                sin_a_act.append(v_a)
                sin_b_act.append(v_b)
                disp_inc_a_list.append(d_sin_a * (intervalo_l * 1000))
                disp_inc_b_list.append(d_sin_b * (intervalo_l * 1000))

        if len(disp_inc_a_list) > 0:
            # ACUMULACIÓN DE ABAJO HACIA ARRIBA (Punto Fijo = 0 mm en la base del filtro)
            inc_a_rev = disp_inc_a_list[::-1]
            inc_b_rev = disp_inc_b_list[::-1]

            acum_a_rev = np.cumsum(inc_a_rev) - inc_a_rev[0]
            acum_b_rev = np.cumsum(inc_b_rev) - inc_b_rev[0]

            disp_acum_a = acum_a_rev[::-1]
            disp_acum_b = acum_b_rev[::-1]
            vector_resultante = np.sqrt(disp_acum_a**2 + disp_acum_b**2)

            df = pd.DataFrame({
                "Nodo": nodos_lista,
                "Profundidad (m)": profundidades,
                "Sin_A": sin_a_act,
                "Sin_B": sin_b_act,
                "Disp_Inc_A (mm)": disp_inc_a_list,
                "Disp_Acum_A (mm)": disp_acum_a,
                "Disp_Inc_B (mm)": disp_inc_b_list,
                "Disp_Acum_B (mm)": disp_acum_b,
                "Vector_Resultante (mm)": vector_resultante,
            })

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
                    title=f"Cumulative Displacement (Deformación Neta hasta {profundidad_max_evaluar:.2f} m) - Eje A [{fecha_sel} vs Base: {fecha_base}]",
                    labels={
                        "Disp_Acum_A (mm)": "Desplazamiento Acumulado (mm)",
                        "Profundidad (m)": "Profundidad (m)",
                    },
                    markers=True,
                    text="Nodo",
                )
                fig_cum.update_yaxes(
                    autorange="reversed", range=[profundidad_max_evaluar, 0]
                )
                fig_cum.add_vline(
                    x=0, line_dash="dash", line_color="red", annotation_text="Línea Base (0 mm)"
                )
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
                    autorange="reversed", range=[profundidad_max_evaluar, 0]
                )
                st.plotly_chart(fig_inc, use_container_width=True)

            # 3. ABSOLUTE PLOT
            with tab_abs:
                fig_abs = px.line(
                    df,
                    x="Sin_A",
                    y="Profundidad (m)",
                    title=f"Absolute Position (Geometría Física de la Tubería) [sin(θ)] [{fecha_sel}]",
                    labels={
                        "Sin_A": "Seno del Ángulo sin(θ)",
                        "Profundidad (m)": "Profundidad (m)",
                    },
                    markers=True,
                    text="Nodo",
                )
                fig_abs.update_yaxes(
                    autorange="reversed", range=[profundidad_instalacion, 0]
                )
                st.plotly_chart(fig_abs, use_container_width=True)

            # 4. TIME PLOT
            with tab_time:
                nodos_disp = [f"Axis A {n.split(' ')[1]}" for n in nodos_lista]
                nodo_sel = st.selectbox(
                    "Selecciona el Sensor a evaluar en el tiempo:", nodos_disp
                )
                fig_time = px.line(
                    df_clean,
                    x="TIMESTAMP",
                    y=nodo_sel,
                    title=f"Time Plot - Evolución Temporal Limpia en {nodo_sel}",
                    labels={"TIMESTAMP": "Fecha / Hora", nodo_sel: "sin(θ)"},
                )
                st.plotly_chart(fig_time, use_container_width=True)

            # 5. VECTOR PLOT
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
                    autorange="reversed", range=[profundidad_max_evaluar, 0]
                )
                st.plotly_chart(fig_vec, use_container_width=True)

            # 6. POLAR PLOT
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
            # 4. TABLA DE RESULTADOS PROCESADOS
            # ---------------------------------------------------------
            st.markdown("---")
            st.subheader(
                f"📋 Tabla de Desplazamiento Neto Limpio — Registro: {fecha_sel} vs Base: {fecha_base} (Hasta {profundidad_max_evaluar:.2f} m)"
            )
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("La profundidad seleccionada es menor al primer nodo.")

    else:
        st.error("El archivo no tiene el formato DT2485 esperado.")
else:
    st.info("👈 Carga el archivo CSV del DT2485 para habilitar la suite IncliAnalysis.")

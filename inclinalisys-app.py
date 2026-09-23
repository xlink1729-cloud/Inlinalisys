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
# FUNCIÓN DE ADAPTACIÓN Y COMPATIBILIDAD DE ARCHIVOS MULTIFORMATO
# ---------------------------------------------------------
def procesar_y_estandarizar_csv(file):
    """
    Detecta automáticamente si el archivo proviene de un logger DT2485
    o de un sistema CR6/ELGL4000 (Inclinómetro IC7570), estandarizando columnas.
    """
    df = pd.read_csv(file)
    cols_originales = df.columns.tolist()

    # Verificación de formato CR6 / ELGL4000
    tiene_sin_angle = any("SIN_Angle" in str(c) for c in cols_originales)

    if tiene_sin_angle:
        nuevas_columnas = []
        nodo_counter = 1

        for col in cols_originales:
            col_str = str(col).strip()
            if "TIMESTAMP" in col_str.upper():
                nuevas_columnas.append("TIMESTAMP")
            elif "RECORD" in col_str.upper():
                nuevas_columnas.append("RECORD")
            elif "SIN_ANGLE" in col_str.upper():
                nuevas_columnas.append(f"Axis A {nodo_counter}")
            elif col_str.upper() == "C" or col_str.startswith("C."):
                nuevas_columnas.append(f"Temp {nodo_counter}")
                nodo_counter += 1
            else:
                nuevas_columnas.append(col)

        df.columns = nuevas_columnas

        # Relleno de seguridad para Eje B en cadenas uniaxiales (IC7570 / CR6)
        # Esto evita fallos al calcular vectores o gráficos biaxiales
        for i in range(1, nodo_counter):
            col_b = f"Axis B {i}"
            if col_b not in df.columns:
                df[col_b] = 0.0

        st.info(
            f"ℹ️ **Formato Detectado:** Registrador Campbell Scientific CR6 / Interfaz ELGL4000 "
            f"({nodo_counter - 1} Nodos detectados - Inclinómetro IC7570)."
        )
    else:
        st.info("ℹ️ **Formato Detectado:** Datalogger RST DT2485.")

    return df


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

intervalo_l = (
    profundidad_instalacion / no_sensores if no_sensores > 0 else 1.98
)
st.sidebar.info(f"📏 Tramo entre nodos: **{intervalo_l:.2f} m**")

# ---------------------------------------------------------
# FILTROS DE PROFUNDIDAD Y PROMEDIO (MEAN)
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("🎯 Filtros y Operaciones")
profundidad_max_evaluar = st.sidebar.slider(
    "Evaluar hasta profundidad (m):",
    min_value=float(intervalo_l),
    max_value=float(profundidad_instalacion),
    value=float(profundidad_instalacion),
    step=float(intervalo_l),
    help="Según la norma ASTM D6230, el cálculo acumulativo debe iniciar en la base fija empotrada.",
)

usar_promedio_mean = st.sidebar.checkbox(
    "📊 Activar Promedio (Mean)",
    value=False,
    help="Promedia lecturas dentro de un rango de tiempo para reducir ruido térmico/eléctrico.",
)

uploaded_file = st.sidebar.file_uploader(
    "Cargar archivo CSV (DT2485 o CR6/ELGL4000)", type=["csv"]
)

# ---------------------------------------------------------
# 2. MÉTRICAS PRINCIPALES
# ---------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pozo", nombre_pozo)
col2.metric("Prof. Evaluar", f"{profundidad_max_evaluar:.2f} m")
col3.metric("Sensores IPI", f"{no_sensores} Nodos")
col4.metric("Azimuth A+", f"{azimut_eje_a}°")
col5.metric(
    "Modo Lectura", "Mean (Promedio)" if usar_promedio_mean else "Punto Único"
)

st.markdown("---")

# ---------------------------------------------------------
# 3. PROCESAMIENTO Y ANÁLISIS
# ---------------------------------------------------------
if uploaded_file is not None:
    # Carga con estandarización universal
    df_raw = procesar_y_estandarizar_csv(uploaded_file)

    cols_sensores = [
        c
        for c in df_raw.columns
        if c.startswith("Axis A") or c.startswith("Axis B")
    ]

    if cols_sensores and "TIMESTAMP" in df_raw.columns:
        # Depuración automática (remueve 0.999998 y lecturas desmedidas)
        df_clean = df_raw.copy()
        num_errores = 0

        for col in cols_sensores:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
            mask_err = (
                (df_clean[col].isna())
                | (df_clean[col].abs() > 0.5)
                | (df_clean[col].round(4) == 0.9999)
            )
            num_errores += mask_err.sum()
            df_clean.loc[mask_err, col] = np.nan

        if num_errores > 0:
            st.warning(
                f"🧹 **Filtro de Limpieza:** Se descartaron **{num_errores} lecturas atípicas (ej. 0.999998)**."
            )

        timestamps = df_clean["TIMESTAMP"].dropna().unique()

        col_f1, col_f2 = st.columns(2)

        if not usar_promedio_mean:
            with col_f1:
                fecha_base = st.selectbox(
                    "🟢 Selecciona Lectura BASE (Inicial / Zero Reading):",
                    timestamps,
                    index=0,
                )
            with col_f2:
                fecha_sel = st.selectbox(
                    "🔴 Selecciona Lectura ACTUAL a Evaluar:",
                    timestamps,
                    index=len(timestamps) - 1,
                )

            fila_base = df_clean[df_clean["TIMESTAMP"] == fecha_base].iloc[0]
            fila_actual = df_clean[df_clean["TIMESTAMP"] == fecha_sel].iloc[0]
        else:
            with col_f1:
                rango_base = st.multiselect(
                    "🟢 Fechas para Lectura BASE (Calcula Mean):",
                    timestamps,
                    default=[timestamps[0]],
                )
            with col_f2:
                rango_actual = st.multiselect(
                    "🔴 Fechas para Lectura ACTUAL (Calcula Mean):",
                    timestamps,
                    default=[timestamps[-1]],
                )

            fecha_base = (
                f"Mean ({len(rango_base)} muestras)"
                if rango_base
                else timestamps[0]
            )
            fecha_sel = (
                f"Mean ({len(rango_actual)} muestras)"
                if rango_actual
                else timestamps[-1]
            )

            df_base_sub = df_clean[
                df_clean["TIMESTAMP"].isin(
                    rango_base if rango_base else [timestamps[0]]
                )
            ]
            df_act_sub = df_clean[
                df_clean["TIMESTAMP"].isin(
                    rango_actual if rango_actual else [timestamps[-1]]
                )
            ]

            fila_base = df_base_sub[cols_sensores].mean()
            fila_actual = df_act_sub[cols_sensores].mean()

        # Recolección y cálculo de deltas
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

                raw_base_b = fila_base.get(col_b, 0.0)
                raw_act_b = fila_actual.get(col_b, 0.0)

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
                    v_b = 0.0
                    d_sin_b = 0.0

                nodos_lista.append(f"Nodo {i}")
                profundidades.append(prof)
                sin_a_act.append(v_a)
                sin_b_act.append(v_b)
                disp_inc_a_list.append(d_sin_a * (intervalo_l * 1000))
                disp_inc_b_list.append(d_sin_b * (intervalo_l * 1000))

        if len(disp_inc_a_list) > 0:
            # Acumulación de abajo hacia arriba (Punto fijo en la base del filtro)
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
            # BARRA DE PESTAÑAS (INCLIANALYSIS SUITE)
            # ---------------------------------------------------------
            (
                tab_cum,
                tab_inc,
                tab_abs,
                tab_mean,
                tab_time,
                tab_vel,
                tab_vector,
                tab_polar,
                tab_normas,
            ) = st.tabs([
                "📊 Acumulativo",
                "📉 Incremental",
                "📐 Absoluto",
                "📈 Análisis Promedio",
                "⏱️ Evolución Temporal",
                "🚀 Tasa de Deformación",
                "🧭 Vector Resultante",
                "🎯 Vista en Planta",
                "📖 Marco Normativo",
            ])

            # 1. CUMULATIVE DISPLACEMENT
            with tab_cum:
                fig_cum = px.line(
                    df,
                    x="Disp_Acum_A (mm)",
                    y="Profundidad (m)",
                    title=f"Desplazamiento Acumulado - Eje A [{fecha_sel} vs Base: {fecha_base}]",
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
                    x=0,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Base (0 mm)",
                )
                st.plotly_chart(fig_cum, use_container_width=True)

            # 2. INCREMENTAL MOVEMENT
            with tab_inc:
                fig_inc = px.line(
                    df,
                    x="Disp_Inc_A (mm)",
                    y="Profundidad (m)",
                    title=f"Movimiento Incremental (Por Tramo) - Eje A [{fecha_sel}]",
                    labels={
                        "Disp_Inc_A (mm)": "Desplazamiento Incremental (mm)",
                        "Profundidad (m)": "Profundidad (m)",
                    },
                    markers=True,
                    text="Nodo",
                )
                fig_inc.update_yaxes(
                    autorange="reversed", range=[profundidad_max_evaluar, 0]
                )
                fig_inc.add_vline(x=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_inc, use_container_width=True)

            # 3. ABSOLUTE POSITION
            with tab_abs:
                fig_abs = px.line(
                    df,
                    x="Sin_A",
                    y="Profundidad (m)",
                    title=f"Posición Absoluta (Geometría Física de la Tubería) [sin(θ)] [{fecha_sel}]",
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

            # 4. MEAN ANALYSIS
            with tab_mean:
                fig_mean = go.Figure()
                fig_mean.add_trace(
                    go.Scatter(
                        x=df["Disp_Acum_A (mm)"],
                        y=df["Profundidad (m)"],
                        mode="lines+markers+text",
                        name="Promedio Acumulado A (mm)",
                        text=df["Nodo"],
                        textposition="top right",
                        line=dict(color="blue", width=2),
                    )
                )
                fig_mean.add_trace(
                    go.Scatter(
                        x=df["Disp_Acum_B (mm)"],
                        y=df["Profundidad (m)"],
                        mode="lines+markers+text",
                        name="Promedio Acumulado B (mm)",
                        text=df["Nodo"],
                        textposition="top right",
                        line=dict(color="green", width=2),
                    )
                )
                fig_mean.update_layout(
                    title="Análisis Estadístico Promedio por Perfil",
                    xaxis_title="Desplazamiento Promedio (mm)",
                    yaxis_title="Profundidad (m)",
                    yaxis=dict(autorange="reversed"),
                    template="plotly_white",
                )
                fig_mean.add_vline(x=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig_mean, use_container_width=True)

            # 5. TIME PLOT
            with tab_time:
                nodos_disp = [f"Axis A {n.split(' ')[1]}" for n in nodos_lista]
                nodo_sel = st.selectbox(
                    "Selecciona el Sensor a evaluar en el tiempo:", nodos_disp
                )
                fig_time = px.line(
                    df_clean,
                    x="TIMESTAMP",
                    y=nodo_sel,
                    title=f"Evolución Temporal en {nodo_sel}",
                    labels={"TIMESTAMP": "Fecha / Hora", nodo_sel: "sin(θ)"},
                )
                st.plotly_chart(fig_time, use_container_width=True)

            # 6. TASA DE DEFORMACIÓN / VELOCIDAD DE MOVIMIENTO
            with tab_vel:
                st.subheader(
                    "🚀 Tasa de Deformación / Velocidad de Movimiento"
                )

                if not usar_promedio_mean:
                    try:
                        t_b = pd.to_datetime(fecha_base)
                        t_a = pd.to_datetime(fecha_sel)
                        dias_transcurridos = (t_a - t_b).days
                    except Exception:
                        dias_transcurridos = 0
                else:
                    dias_transcurridos = 30

                if dias_transcurridos <= 0:
                    st.warning(
                        "⚠️ Para calcular la tasa de velocidad, la **Lectura ACTUAL** debe ser posterior en el tiempo a la **Lectura BASE**."
                    )
                else:
                    meses_transcurridos = dias_transcurridos / 30.4375

                    df["Velocidad_A (mm/mes)"] = (
                        df["Disp_Acum_A (mm)"] / meses_transcurridos
                    )
                    df["Velocidad_B (mm/mes)"] = (
                        df["Disp_Acum_B (mm)"] / meses_transcurridos
                    )

                    idx_max = df["Velocidad_A (mm/mes)"].abs().idxmax()
                    nodo_critico = df.loc[idx_max, "Nodo"]
                    vel_max = df.loc[idx_max, "Velocidad_A (mm/mes)"]
                    prof_critica = df.loc[idx_max, "Profundidad (m)"]
                    disp_max = df.loc[idx_max, "Disp_Acum_A (mm)"]

                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric(
                        "Tiempo Transcurrido",
                        f"{dias_transcurridos} días",
                        f"{meses_transcurridos:.1f} meses",
                    )
                    kpi2.metric(
                        f"Velocidad Máxima ({nodo_critico})",
                        f"{abs(vel_max):.3f} mm/mes",
                        f"A {prof_critica:.2f} m prof.",
                        delta_color="off",
                    )
                    kpi3.metric(
                        "Desplazamiento Acumulado Máx.",
                        f"{disp_max:.2f} mm",
                        "Eje A",
                    )

                    vel_abs = abs(vel_max)
                    if vel_abs < 0.5:
                        st.success(
                            "🟢 **Estado: ESTABLE (Alerta Verde)** — La velocidad de deformación es menor a 0.5 mm/mes. Comportamiento dentro de tolerancias normales."
                        )
                    elif 0.5 <= vel_abs <= 2.0:
                        st.warning(
                            "🟡 **Estado: PRECAUCIÓN (Alerta Amarilla)** — Velocidad entre 0.5 y 2.0 mm/mes. Se sugiere monitorear con mayor frecuencia."
                        )
                    else:
                        st.error(
                            "🔴 **Estado: CRÍTICO (Alerta Roja)** — Velocidad superior a 2.0 mm/mes. Aceleración registrada. Notificar al especialista geotécnico."
                        )

                    fig_vel = go.Figure()
                    fig_vel.add_trace(
                        go.Scatter(
                            x=df["Velocidad_A (mm/mes)"],
                            y=df["Profundidad (m)"],
                            mode="lines+markers+text",
                            name="Velocidad Eje A (mm/mes)",
                            text=df["Nodo"],
                            textposition="top right",
                            line=dict(color="#2ca02c", width=2.5),
                            marker=dict(size=8, symbol="diamond"),
                        )
                    )
                    fig_vel.add_vline(
                        x=0, line_dash="dash", line_color="gray", opacity=0.7
                    )
                    fig_vel.update_layout(
                        title=f"Perfil de Velocidad de Movimiento [{fecha_sel} vs Base: {fecha_base}]",
                        xaxis_title="Velocidad de Deformación (mm/mes)",
                        yaxis_title="Profundidad (m)",
                        yaxis=dict(autorange="reversed"),
                        template="plotly_white",
                        height=550,
                    )
                    st.plotly_chart(fig_vel, use_container_width=True)

            # 7. VECTOR PLOT
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
                    text="Nodo",
                )
                fig_vec.update_yaxes(
                    autorange="reversed", range=[profundidad_max_evaluar, 0]
                )
                st.plotly_chart(fig_vec, use_container_width=True)

            # 8. POLAR PLOT
            with tab_polar:
                fig_polar = px.scatter(
                    df,
                    x="Disp_Acum_A (mm)",
                    y="Disp_Acum_B (mm)",
                    color="Nodo",
                    text="Nodo",
                    title=f"Vista en Planta / Deformación Bi-Axial (A vs B) [{fecha_sel}]",
                    labels={
                        "Disp_Acum_A (mm)": "Eje A (mm)",
                        "Disp_Acum_B (mm)": "Eje B (mm)",
                    },
                )
                fig_polar.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_polar.add_vline(x=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_polar, use_container_width=True)

            # 9. MARCO NORMATIVO Y FUNDAMENTO TÉCNICO
            with tab_normas:
                st.subheader(
                    "📖 Marco Normativo y Fundamentos Geotécnicos"
                )

                col_n1, col_n2 = st.columns(2)

                with col_n1:
                    st.markdown("""
                    ### 📐 Norma ASTM D6230
                    *Standard Test Method for Monitoring Ground Movement Using Inclinometers*

                    El procesamiento matemático ejecutado en esta plataforma sigue estrictamente las especificaciones de la norma internacional **ASTM D6230**:

                    1. **Geometría del Sensor:** La deformación incremental por tramo ($\delta_i$) se calcula convirtiendo la lectura de salida en seno del ángulo ($\sin\\theta$) a desplazamiento lineal mediante:
                       $$\delta_i = (\sin\\theta_{\text{actual}} - \sin\\theta_{\text{base}}) \times L$$
                       *Donde $L$ es la distancia entre centros de sensores ($1.98\text{ m} = 1980\text{ mm}$).*

                    2. **Condición de Borde Fijo (Anclaje Inferior):** De acuerdo con el estándar, el extremo inferior empotrado en terreno firme o roca sana es considerado como el **origen estático inamovible ($0.00\text{ mm}$)**, acumulando los desplazamientos de abajo hacia arriba (`bottom-up`).
                    """)

                with col_n2:
                    st.markdown("""
                    ### 🚦 Umbrales de Seguridad (Dunnicliff, 1993)
                    *Geotechnical Instrumentation for Monitoring Field Performance*

                    Los semáforos de alerta configurados en la pestaña **Tasa de Deformación** se fundamentan en los criterios de velocidad recomendados por Dunnicliff y el US Army Corps of Engineers (USACE):

                    * **🟢 Alerta Verde (< 0.5 mm/mes):** Movimientos dentro del rango de variaciones elásticas normales del terreno o fluctuaciones por dilatación térmica.
                    * **🟡 Alerta Amarilla (0.5 – 2.0 mm/mes):** Tasa de deformación continua observable. Se requiere incrementar la frecuencia de monitoreo y evaluar condiciones hidráulicas/carga.
                    * **🔴 Alerta Roja (> 2.0 mm/mes):** Tasa de aceleración crítica de la masa del terreno. Requiere aviso inmediato al especialista geotécnico para implementar medidas de mitigación.
                    """)

                st.info(
                    "💡 **Nota de Cumplimiento:** El módulo de depuración automática remueve lecturas erróneas fuera del rango $[-0.5, 0.5] \\sin\\theta$ o códigos de falla del datalogger (`0.999998`), cumpliendo con los controles de calidad de datos exigidos por la norma."
                )

            # ---------------------------------------------------------
            # 4. TABLA DE RESULTADOS PROCESADOS
            # ---------------------------------------------------------
            st.markdown("---")
            st.subheader(
                f"📋 Tabla de Desplazamientos Procesados — Registro: {fecha_sel} vs Base: {fecha_base}"
            )
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("La profundidad seleccionada es menor al primer nodo.")

    else:
        st.error("El archivo cargado no contiene columnas reconocibles de sensores DT2485 ni CR6.")
else:
    st.info(
        "👈 Carga un archivo CSV (DT2485 o CR6/ELGL4000) para habilitar la suite IncliAnalysis."
    )

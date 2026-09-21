import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Sistema RST IPI - Análisis Inclinométrico", layout="wide"
)
st.title("📊 Procesador de Inclinómetro In-Situ (RST IPI)")

# ---------------------------------------------------------
# 1. METADATOS Y PARÁMETROS DE CONFIGURACIÓN
# ---------------------------------------------------------
st.sidebar.header("📍 Parámetros del Pozo")
nombre_pozo = st.sidebar.text_input("Identificador", value="PZ-01")
profundidad_total = st.sidebar.number_input(
    "Profundidad de Instalación (m)", value=23.77, step=0.01
)
no_sensores = st.sidebar.number_input("Número de Nodos", value=12, step=1)
azimut_eje_a = st.sidebar.number_input("Azimuth Eje A+ (°)", value=5.32)

intervalo_l = (
    profundidad_total / no_sensores if no_sensores > 0 else 1.98
)  # ~1.98 m
st.sidebar.info(f"📏 Intervalo por sensor: **{intervalo_l:.2f} m**")

# Carga del archivo CSV limpio
uploaded_file = st.sidebar.file_uploader("Cargar CSV Limpio", type=["csv"])

# ---------------------------------------------------------
# 2. PROCESAMIENTO DE DATOS DE ARCHIVO DE DATALOGGER
# ---------------------------------------------------------
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("📋 Vista Previa de Datos")
    st.dataframe(df.head(5), use_container_width=True)

    # Identificar columnas de sensores Axis A
    col_axis_a = [c for c in df.columns if c.startswith("Axis A")]
    col_axis_b = [c for c in df.columns if c.startswith("Axis B")]

    if col_axis_a and "TIMESTAMP" in df.columns:
        # Selector de Fecha / Lectura
        st.markdown("---")
        timestamps = df["TIMESTAMP"].unique()
        fecha_seleccionada = st.selectbox(
            "🕒 Selecciona la Fecha y Hora de Lectura:", timestamps
        )

        # Fila correspondiente a la fecha seleccionada
        fila_data = df[df["TIMESTAMP"] == fecha_seleccionada].iloc[0]

        # Construir DataFrame por Sensor para esa lectura
        datos_nodos = []

        # El sensor 1 está arriba y el sensor N al fondo (o viceversa)
        for i in range(1, no_sensores + 1):
            col_a = f"Axis A {i}"
            col_b = f"Axis B {i}"

            sin_a = fila_data.get(col_a, np.nan)
            sin_b = fila_data.get(col_b, np.nan)

            # Filtrar lecturas de error (ej. 0.999998)
            if abs(sin_a) > 0.5:
                sin_a = np.nan
            if abs(sin_b) > 0.5:
                sin_b = np.nan

            # Profundidad desde la superficie
            prof = i * intervalo_l

            datos_nodos.append(
                {
                    "Nodo": f"Sensor {i}",
                    "Profundidad_m": prof,
                    "Sin_A": sin_a,
                    "Sin_B": sin_b,
                    # Desplazamiento incremental = sin(theta) * L (en mm)
                    "Disp_Inc_A_mm": (
                        sin_a * (intervalo_l * 1000)
                        if pd.notnull(sin_a)
                        else 0
                    ),
                    "Disp_Inc_B_mm": (
                        sin_b * (intervalo_l * 1000)
                        if pd.notnull(sin_b)
                        else 0
                    ),
                }
            )

        df_procesado = pd.DataFrame(datos_nodos)

        # Ordenar desde el fondo para la suma acumulada
        df_procesado = df_procesado.sort_values(
            by="Profundidad_m", ascending=False
        )
        df_procesado["Disp_Acum_A_mm"] = df_procesado[
            "Disp_Inc_A_mm"
        ].cumsum()
        df_procesado["Disp_Acum_B_mm"] = df_procesado[
            "Disp_Inc_B_mm"
        ].cumsum()

        # Volver a ordenar por profundidad descendente para graficar
        df_procesado = df_procesado.sort_values(
            by="Profundidad_m", ascending=True
        )

        # ---------------------------------------------------------
        # 3. VISUALIZACIÓN DE GRÁFICAS (EJE A Y EJE B)
        # ---------------------------------------------------------
        st.subheader(f"📈 Perfil Inclinométrico - {fecha_seleccionada}")

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig_a = px.line(
                df_procesado,
                x="Disp_Acum_A_mm",
                y="Profundidad_m",
                title="Eje Principal (A) - Desplazamiento Acumulado",
                labels={
                    "Disp_Acum_A_mm": "Desplazamiento (mm)",
                    "Profundidad_m": "Profundidad (m)",
                },
                markers=True,
                text="Nodo",
            )
            fig_a.update_yaxes(autorange="reversed")
            fig_a.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_a, use_container_width=True)

        with col_g2:
            fig_b = px.line(
                df_procesado,
                x="Disp_Acum_B_mm",
                y="Profundidad_m",
                title="Eje Transversal (B) - Desplazamiento Acumulado",
                labels={
                    "Disp_Acum_B_mm": "Desplazamiento (mm)",
                    "Profundidad_m": "Profundidad (m)",
                },
                markers=True,
                text="Nodo",
            )
            fig_b.update_yaxes(autorange="reversed")
            fig_b.add_vline(x=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_b, use_container_width=True)

        st.subheader("📄 Tabla de Resultados Procesados")
        st.dataframe(
            df_procesado[
                [
                    "Nodo",
                    "Profundidad_m",
                    "Sin_A",
                    "Disp_Inc_A_mm",
                    "Disp_Acum_A_mm",
                    "Sin_B",
                    "Disp_Inc_B_mm",
                    "Disp_Acum_B_mm",
                ]
            ],
            use_container_width=True,
        )

    else:
        st.error(
            "El archivo no contiene las columnas 'TIMESTAMP' o 'Axis A 1'..."
        )
else:
    st.info("👈 Por favor carga el archivo CSV procesado en el panel izquierdo.")

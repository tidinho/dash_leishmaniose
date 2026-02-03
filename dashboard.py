import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium



# ==================================================
# CONFIGURAÇÃO
# ==================================================
st.set_page_config(
    page_title="Leishmaniose - Dashboard Epidemiológico",
    layout="wide"
)

st.title("🦟 Dashboard Epidemiológico de Leishmaniose")
st.markdown("Análise espacial, socioeconômica e ambiental dos casos")

# ==================================================
# CARREGAMENTO DOS DADOS
# ==================================================
df = pd.read_parquet("mega_tratados.parquet")



# ==================================================
# TRATAMENTO DE DADOS
# ==================================================

# Data de notificação (fonte única)
df["dt_notific"] = (
    df["dt_notific"]
    .astype(str)
    .str.strip()
)

df["dt_notific"] = pd.to_datetime(
    df["dt_notific"],
    errors="coerce",
    dayfirst=True
)

df["ano_notificacao"] = df["dt_notific"].dt.year.astype("Int64")

# 1 linha = 1 caso
df["casos"] = 1

# Conversões numéricas
num_cols = [
    "lat_locali",
    "long_local",
    "idh",
    "renda_media",
    "precipitacao_mensal"
]

for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Saneamento básico
if "saneamento_basico" in df.columns:
    df["saneamento_basico"] = (
        df["saneamento_basico"]
        .astype(str)
        .str.replace(",", ".", regex=False)
    )
    df["saneamento_basico"] = pd.to_numeric(
        df["saneamento_basico"], errors="coerce"
    )

# ==================================================
# FILTROS (SIDEBAR)
# ==================================================
st.sidebar.header("🎛️ Filtros")

# UF (global)
ufs = sorted(df["sigla_uf"].dropna().unique())
uf_sel = st.sidebar.multiselect("Estado (UF)", ufs, default=ufs)
df_uf = df[df["sigla_uf"].isin(uf_sel)]

# Município (depende da UF)
municipios = sorted(df_uf["nm_mun"].dropna().unique())
mun_sel = st.sidebar.multiselect("Município", municipios)
df_mun = df_uf if not mun_sel else df_uf[df_uf["nm_mun"].isin(mun_sel)]

# Unidade notificadora (depende do município)
unidades = sorted(df_mun["no_fantasia"].dropna().unique())
uni_sel = st.sidebar.multiselect("Unidade notificadora", unidades)
df_uni = df_mun if not uni_sel else df_mun[df_mun["no_fantasia"].isin(uni_sel)]

# ANO (DOMÍNIO GLOBAL — CORREÇÃO PRINCIPAL)
anos = sorted(df["ano_notificacao"].dropna().unique())

ano_sel = st.sidebar.multiselect(
    "Ano de notificação",
    anos,
    default=anos
)

df_filt = (
    df_uni
    if not ano_sel
    else df_uni[df_uni["ano_notificacao"].isin(ano_sel)]
)

# ==================================================
# KPIs
# ==================================================
st.subheader("📌 Indicadores Gerais")

c1, c2, c3 = st.columns(3)
c1.metric("Total de casos", int(df_filt["casos"].sum()))
c2.metric("Municípios afetados", df_filt["nm_mun"].nunique())
c3.metric("Unidades notificadoras", df_filt["no_fantasia"].nunique())

# ==================================================
# CASOS POR ESTADO
# ==================================================
st.subheader("📊 Casos por Estado")

casos_uf = (
    df_filt
    .groupby("sigla_uf", as_index=False)
    .agg(casos=("casos", "sum"))
)

fig_uf = px.bar(
    casos_uf,
    x="sigla_uf",
    y="casos",
    labels={"sigla_uf": "Estado", "casos": "Casos"}
)

st.plotly_chart(fig_uf, use_container_width=True)

# ==================================================
# CASOS POR MUNICÍPIO
# ==================================================
st.subheader("🏙️ Casos por Município (Top 20)")

casos_mun = (
    df_filt
    .groupby(["nm_mun", "sigla_uf"], as_index=False)
    .agg(casos=("casos", "sum"))
    .sort_values("casos", ascending=False)
    .head(20)
)

fig_mun = px.bar(
    casos_mun,
    x="casos",
    y="nm_mun",
    color="sigla_uf",
    orientation="h"
)

st.plotly_chart(fig_mun, use_container_width=True)

# ==================================================
# MAPA
# ==================================================
st.subheader("🗺️ Distribuição Geográfica dos Casos")

map_df = (
    df_filt
    .dropna(subset=["lat_locali", "long_local"])
    .groupby(["nm_mun", "lat_locali", "long_local"], as_index=False)
    .agg(casos=("casos", "sum"))
)

m = folium.Map(location=[-14.5, -52], zoom_start=4, tiles="cartodbpositron")

for _, row in map_df.iterrows():
    folium.CircleMarker(
        location=[row["lat_locali"], row["long_local"]],
        radius=min(row["casos"] / 2, 15),
        color="red",
        fill=True,
        fill_opacity=0.6,
        tooltip=f"<b>{row['nm_mun']}</b><br>Casos: {int(row['casos'])}"
    ).add_to(m)

st_folium(m, width=1200, height=500)

# ==================================================
# HEATMAP
# ==================================================
st.subheader("🔥 Heatmap Espacial – Concentração de Casos")

heat_df = (
    df_filt
    .dropna(subset=["lat_locali", "long_local"])
    .groupby(["lat_locali", "long_local"], as_index=False)
    .agg(peso=("casos", "sum"))
)

radius = st.slider("Raio do Heatmap", 5, 40, 20)
blur = st.slider("Blur", 5, 30, 15)

m_heat = folium.Map(location=[-14.5, -52], zoom_start=4, tiles="cartodbpositron")

HeatMap(
    heat_df[["lat_locali", "long_local", "peso"]].values.tolist(),
    radius=radius,
    blur=blur,
    max_zoom=10
).add_to(m_heat)

st_folium(m_heat, width=1200, height=500)

# ==================================================
# CASOS x INDICADORES
# ==================================================
st.subheader("📈 Casos x Indicadores Socioambientais")

indicador = st.selectbox(
    "Selecione o indicador",
    ["idh", "saneamento_basico", "renda_media", "precipitacao_mensal"]
)

rel_df = (
    df_filt
    .groupby("nm_mun", as_index=False)
    .agg(
        casos=("casos", "sum"),
        idh=("idh", "mean"),
        saneamento=("saneamento_basico", "mean"),
        renda=("renda_media", "mean"),
        precipitacao=("precipitacao_mensal", "mean")
    )
)

map_ind = {
    "idh": "idh",
    "saneamento_basico": "saneamento",
    "renda_media": "renda",
    "precipitacao_mensal": "precipitacao"
}

fig_corr = px.scatter(
    rel_df,
    x=map_ind[indicador],
    y="casos",
    trendline="ols",
    labels={"casos": "Total de Casos"}
)

st.plotly_chart(fig_corr, use_container_width=True)

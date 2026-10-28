from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st
import yfinance as yf

# 1. Configuração da Página em modo WIDE
st.set_page_config(
    page_title="PRO TERMINAL | B3 & Carteira",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. CSS Profissional (Estilo Terminal / Pro Trader) & Responsivo
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .main .block-container {
        padding: 1.5rem 1.5rem !important;
        max-width: 1400px !important;
    }

    #MainMenu, footer, header {visibility: hidden;}

    /* Tema Dark Pro (Estilo Terminal Financeiro) */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, sans-serif;
        font-variant-numeric: tabular-nums;
    }

    h1, h2, h3 {
        color: #f8fafc;
        font-weight: 600;
        letter-spacing: -0.5px;
    }

    /* Botões Profissionais */
    .stButton>button {
        background-color: #1f2937;
        color: #f8fafc;
        border: 1px solid #374151;
        border-radius: 6px;
        font-weight: 600;
        height: 40px;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #374151;
        border-color: #10b981;
        color: #10b981;
    }

    /* Campos de Entrada */
    .stTextInput input, .stNumberInput input, select {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #111827 !important;
        border: 1px solid #374151 !important;
        border-radius: 6px !important;
        color: #f8fafc !important;
    }

    /* Tabelas com Tipografia Monospaçada Alinhada */
    [data-testid="stDataFrame"] {
        font-family: 'JetBrains Mono', monospace;
        border: 1px solid #1f2937;
        border-radius: 8px;
        background-color: #111827;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- BANCO DE DADOS SQLite ---
def conectar_bd():
    return sqlite3.connect("carteira.db", check_same_thread=False)


def inicializar_bd():
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS carteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simbolo TEXT NOT NULL UNIQUE,
            quantidade INTEGER NOT NULL,
            preco_medio REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


inicializar_bd()


def carregar_carteira():
    conn = conectar_bd()
    df = pd.read_sql_query("SELECT * FROM carteira", conn)
    conn.close()
    return df


def salvar_ativo(simbolo, qtd, preco):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT quantidade, preco_medio FROM carteira WHERE simbolo = ?",
        (simbolo,),
    )
    res = cursor.fetchone()
    if res:
        q_ant, pm_ant = res
        nova_q = q_ant + qtd
        novo_pm = ((q_ant * pm_ant) + (qtd * preco)) / nova_q
        cursor.execute(
            "UPDATE carteira SET quantidade = ?, preco_medio = ? WHERE simbolo = ?",
            (nova_q, novo_pm, simbolo),
        )
    else:
        cursor.execute(
            "INSERT INTO carteira (simbolo, quantidade, preco_medio) VALUES (?, ?, ?)",
            (simbolo, qtd, preco),
        )
    conn.commit()
    conn.close()


def deletar_ativo(simbolo):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carteira WHERE simbolo = ?", (simbolo,))
    conn.commit()
    conn.close()


# Lista Padrão de Monitoramento
ATIVOS_PADRAO = [
    "MXRF11",
    "VGIR11",
    "CPTS11",
    "VGHF11",
    "KISU11",
    "GARE11",
    "TGAR11",
    "KNCR11",
    "PETR4",
    "VALE3",
    "ITUB4",
    "BBAS3",
    "WEGE3",
]


def analisar_oportunidade(preco, minima, maxima, var_pct):
    if var_pct <= -0.5 and preco <= (minima * 1.01):
        return "🟢 BOA PARA COMPRAR"
    elif var_pct >= 1.5:
        return "🔴 AGUARDAR"
    else:
        return "🟡 NEUTRO"


@st.cache_data(ttl=30)
def carregar_dados_mercado(tickers):
    dados = []
    hora_atualizacao = datetime.now().strftime("%H:%M:%S")

    for ticker in tickers:
        ticker_sa = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
        ativo = yf.Ticker(ticker_sa)
        info = ativo.info

        preco = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)
        fech_anterior = info.get("previousClose") or info.get(
            "regularMarketPreviousClose", preco
        )

        var = preco - fech_anterior if preco and fech_anterior else 0.0
        var_pct = (var / fech_anterior * 100) if fech_anterior else 0.0

        minima = info.get("dayLow") or info.get("regularMarketDayLow", preco)
        maxima = info.get("dayHigh") or info.get("regularMarketDayHigh", preco)
        volume = info.get("volume") or info.get("regularMarketVolume", 0)

        recomendacao = analisar_oportunidade(preco, minima, maxima, var_pct)

        dados.append({
            "Símbolo": ticker.replace(".SA", ""),
            "Nome": info.get("shortName", ticker),
            "Preço_Num": preco,
            "Var_Num": var,
            "Var_Pct_Num": var_pct,
            "Volume_Num": volume,
            "Máx.": maxima,
            "Mín.": minima,
            "Avaliação": recomendacao,
        })

    return pd.DataFrame(dados), hora_atualizacao


# Modal Popup do Ranking Tático de Compras
@st.dialog("🏆 RANKING TÁTICO DE COMPRAS")
def abrir_modal_ranking(df):
    st.caption(
        "Ativos ordenados prioritariamente pelas melhores oportunidades de entrada no dia:"
    )
    df_ranking = df.copy()
    ordem_status = {
        "🟢 BOA PARA COMPRAR": 1,
        "🟡 NEUTRO": 2,
        "🔴 AGUARDAR": 3,
    }
    df_ranking["Prioridade"] = df_ranking["Avaliação"].map(ordem_status)
    df_ranking = df_ranking.sort_values(
        by=["Prioridade", "Var_Pct_Num"], ascending=[True, True]
    )

    df_exibicao = pd.DataFrame({
        "Posição": [f"{i+1}º" for i in range(len(df_ranking))],
        "Símbolo": df_ranking["Símbolo"],
        "Preço Atual": df_ranking["Preço_Num"].apply(lambda x: f"R$ {x:.2f}"),
        "Variação %": df_ranking["Var_Pct_Num"].apply(lambda x: f"{x:+.2f}%"),
        "Status de Compra": df_ranking["Avaliação"],
    })

    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)


# --- CABEÇALHO PROFISSIONAL RESPONSIVO ---
st.markdown(
    """
    <style>
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 20px;
        gap: 15px;
    }
    .header-title {
        margin: 0;
        color: #f8fafc;
        font-weight: 700;
        font-size: 1.25rem;
    }
    .header-subtitle {
        margin: 0;
        color: #9ca3af;
        font-size: 12px;
    }
    .badge-ao-vivo {
        background: #064e3b;
        border: 1px solid #10b981;
        color: #34d399;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
    }
    @media (max-width: 640px) {
        .header-container {
            flex-direction: column;
            align-items: flex-start;
        }
        .badge-ao-vivo {
            align-self: flex-start;
        }
    }
    </style>

    <div class="header-container">
        <div>
            <h2 class="header-title">⚡ B3 PRO TERMINAL & CARTEIRA</h2>
            <p class="header-subtitle">Monitoramento de Ativos e Gestão de Posições</p>
        </div>
        <div>
            <span class="badge-ao-vivo">🟢 AO VIVO</span>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

# --- ABAS DE NAVEGAÇÃO PRINCIPAL ---
aba_mercado, aba_carteira = st.tabs(
    ["📊 Monitor de Mercado (B3)", "💼 Minha Carteira"]
)

# ==========================================
# ABA 1: MONITOR DE MERCADO & RANKING
# ==========================================
with aba_mercado:
    col_inp, col_bt1, col_bt2 = st.columns([3, 1, 1])
    with col_inp:
        tickers_input = st.text_input(
            "Ativos (separados por vírgula):",
            ", ".join(ATIVOS_PADRAO),
            label_visibility="collapsed",
        )
        lista_t = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    with col_bt1:
        if st.button("🔄 ATUALIZAR", use_container_width=True):
            st.cache_data.clear()
    with col_bt2:
        btn_ranking = st.button("🏆 RANKING", use_container_width=True)

    with st.spinner("Sincronizando com a B3..."):
        df_mercado, ultima_atualizacao = carregar_dados_mercado(lista_t)

    # Exibição do horário da última atualização
    st.caption(f"🕒 **Última atualização:** {ultima_atualizacao}")

    if btn_ranking:
        abrir_modal_ranking(df_mercado)

    df_exibicao_mercado = pd.DataFrame({
        "Símbolo": df_mercado["Símbolo"],
        "Nome": df_mercado["Nome"],
        "Preço Atual": df_mercado["Preço_Num"].apply(lambda x: f"R$ {x:.2f}"),
        "Var. R$": df_mercado["Var_Num"].apply(lambda x: f"R$ {x:+.2f}"),
        "Var. %": df_mercado["Var_Pct_Num"].apply(lambda x: f"{x:+.2f}%"),
        "Volume": df_mercado["Volume_Num"].apply(
            lambda x: f"{x:,.0f}".replace(",", ".")
        ),
        "Máx. Dia": df_mercado["Máx."].apply(lambda x: f"R$ {x:.2f}"),
        "Mín. Dia": df_mercado["Mín."].apply(lambda x: f"R$ {x:.2f}"),
        "Status Tático": df_mercado["Avaliação"],
    })

    st.dataframe(
        df_exibicao_mercado, use_container_width=True, hide_index=True
    )

# ==========================================
# ABA 2: MINHA CARTEIRA (SQLite)
# ==========================================
with aba_carteira:
    st.subheader("➕ Adicionar / Atualizar Posição")

    with st.form("form_carteira_pro", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
        with c1:
            t_input = st.text_input("Ticker (ex: BBAS3)").upper()
        with c2:
            q_input = st.number_input("Quantidade", min_value=1, value=1)
        with c3:
            p_input = st.number_input(
                "Preço Médio (R$)", min_value=0.01, value=10.00, step=0.01
            )
        with c4:
            st.markdown(
                "<div style='height: 28px;'></div>", unsafe_allow_html=True
            )
            submit_form = st.form_submit_button(
                "Salvar no Banco", use_container_width=True
            )

        if submit_form:
            if t_input:
                salvar_ativo(t_input, q_input, p_input)
                st.success(f"Ativo {t_input} gravado com sucesso no SQLite!")
                st.rerun()

    st.markdown("---")

    # Carregar dados do Banco e Cotações Atuais
    df_db = carregar_carteira()

    if df_db.empty:
        st.info(
            "Sua carteira no banco de dados está vazia. Adicione ativos acima."
        )
    else:
        tickers_carteira = df_db["simbolo"].tolist()
        df_cotacoes, _ = carregar_dados_mercado(tickers_carteira)
        mapa_p = dict(
            zip(df_cotacoes["Símbolo"], df_cotacoes["Preço_Num"])
        )

        tabela_pnl = []
        t_investido = 0.0
        t_atual = 0.0

        for _, row in df_db.iterrows():
            s = row["simbolo"]
            q = row["quantidade"]
            pm = row["preco_medio"]
            p_hoje = mapa_p.get(s, pm)

            custo = q * pm
            valor = q * p_hoje
            lucro = valor - custo
            rent = (lucro / custo * 100) if custo > 0 else 0.0

            t_investido += custo
            t_atual += valor

            tabela_pnl.append({
                "Ativo": s,
                "Qtd": q,
                "Preço Médio": f"R$ {pm:.2f}",
                "Custo Total": f"R$ {custo:.2f}",
                "Preço Atual": f"R$ {p_hoje:.2f}",
                "Valor Hoje": f"R$ {valor:.2f}",
                "Resultado (P&L)": f"R$ {lucro:+.2f} ({rent:+.2f}%)",
            })

        lucro_geral = t_atual - t_investido
        rent_geral = (
            (lucro_geral / t_investido * 100) if t_investido > 0 else 0.0
        )

        # Cartões de Resumo Executivo
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Capital Investido", f"R$ {t_investido:.2f}")
        col_m2.metric("Valor Atual de Mercado", f"R$ {t_atual:.2f}")
        col_m3.metric(
            "Lucro / Prejuízo Total",
            f"R$ {lucro_geral:+.2f}",
            f"{rent_geral:+.2f}%",
        )

        st.markdown("---")
        st.subheader("📋 Posições Atuais Registradas")

        col_tbl, col_del = st.columns([3.5, 1.5])

        with col_tbl:
            st.dataframe(
                pd.DataFrame(tabela_pnl),
                use_container_width=True,
                hide_index=True,
            )

        with col_del:
            st.subheader("Remover Ativo")
            ativo_del = st.selectbox(
                "Selecionar para apagar",
                tickers_carteira,
                label_visibility="collapsed",
            )
            if st.button("🗑️ Apagar do Banco", use_container_width=True):
                deletar_ativo(ativo_del)
                st.success(f"{ativo_del} removido do SQLite!")
                st.rerun()
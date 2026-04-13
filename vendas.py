import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import base64

# ==========================================
# CONFIGURAÇÃO DE TEMA (COR DE FUNDO + MODO CLARO)
# ==========================================
custom_css = """
<style>
    /* 1. CORES DE FUNDO DO SITE */
    [data-testid="stAppViewContainer"] {
        background-color: #718f98; 
    }
    [data-testid="stHeader"] {
        background-color: #fab0b8;
    }
    [data-testid="stSidebar"] {
        background-color: #b2ccd3;
    }

    /* 2. TEXTO GERAL (BRANCO) */
    .stApp, .stMarkdown, p, h1, h2, h3, label, .stSelectbox label, .stTextInput label {
        color: #ffffff !important;
    }

    /* 3. BOTÕES - MODO ESCURO (padrão) */
    div.stButton > button {
        background-color: #333333 !important;
        background: #333333 !important;
        color: #ffffff !important;
        border: 0px solid #555555 !important;
        font-weight: 500;
    }

    /* 4. BOTÕES NO MODO CLARO DO CELULAR */
    @media (prefers-color-scheme: light) {
        div.stButton > button {
            background-color: #ffffff !important;
            background: #ffffff !important;
            color: #000000 !important;
            border: 0px solid #333333 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        div.stButton > button span,
        div.stButton > button p,
        div.stButton > button div {
            color: #000000 !important;
        }
    }

    /* 5. BOTÃO PRIMÁRIO */
    div.stButton > button[kind="primary"] {
        background-color: #0066cc !important;
        color: #ffffff !important;
    }

    @media (prefers-color-scheme: light) {
        div.stButton > button[kind="primary"] {
            background-color: #0066cc !important;
            color: #ffffff !important;
        }
    }

    /* 6. TÍTULOS DAS SEÇÕES DE PRODUTOS (NOVO / EDITAR) - FICAM PRETOS NO MODO CLARO */
    .stExpander > div > div > div > h2,
    .stExpander > div > div > div > h3,
    .stExpander label > div > p,
    section[data-testid="stExpander"] h2,
    section[data-testid="stExpander"] h3 {
        color: #ffffff !important;
    }

    @media (prefers-color-scheme: light) {
        .stExpander > div > div > div > h2,
        .stExpander > div > div > div > h3,
        .stExpander label > div > p,
        section[data-testid="stExpander"] h2,
        section[data-testid="stExpander"] h3 {
            color: #000000 !important;   /* Título preto no modo claro */
        }
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)
# =========================
# CONEXÃO E FUNÇÕES BASE (COM CACHE)
# =========================
@st.cache_resource
def get_spreadsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        spreadsheet_name = st.secrets["spreadsheet_name"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(spreadsheet_name)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        st.stop()

sheet = get_spreadsheet()
ws_vendas = sheet.worksheet("vendas")
ws_usuarios = sheet.worksheet("usuarios")
ws_produtos = sheet.worksheet("produtos")

@st.cache_data(ttl=600)
def get_users_df():
    df = pd.DataFrame(ws_usuarios.get_all_records())
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

@st.cache_data(ttl=600)
def get_products_df():
    data = ws_produtos.get_all_records()
    if not data:
        return pd.DataFrame(columns=['produto', 'preco', 'custo', 'status'])
    df = pd.DataFrame(data)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if 'status' in df.columns:
        return df[df['status'] != 'Oculto']
    return df

@st.cache_data(ttl=600)
def get_vendas_data():
    return ws_vendas.get_all_records()

# =========================
# SISTEMA DE LOGIN E SEGURANÇA
# =========================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.logged_in:
    def get_base64_image(image_path):
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except:
            return None

    img_base64 = get_base64_image("logo.png")

    if img_base64:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
                <img src="data:image/png;base64,{img_base64}" style="width: 40px; margin-right: 15px;">
                <h1 style="margin: 0;">Vendas bb.arte</h1>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.title("🛍️ Vendas bb.arte")
    
    tab_login, tab_esqueci = st.tabs(["Login", "Esqueci minha senha"])
    df_u = get_users_df()
    
    with tab_login:
        user_sel = st.selectbox("Usuário", df_u['nome'].tolist(), key="login_user")
        pwd_input = st.text_input("Senha", type="password", key="login_pwd")
        if st.button("Entrar", use_container_width=True):
            user_info = df_u[df_u['nome'] == user_sel].iloc[0]
            if str(pwd_input) == str(user_info['senha']):
                st.session_state.logged_in = True
                st.session_state.user = user_sel
                st.session_state.role = user_info['role']
                st.rerun()
            else:
                st.error("Senha incorreta.")

    with tab_esqueci:
        st.subheader("Redefinição de Segurança")
        user_reset = st.selectbox("Selecione seu usuário", df_u['nome'].tolist(), key="reset_user")
        user_code_input = st.text_input("Digite seu Código de Recuperação", type="password")
        nova_pwd = st.text_input("Nova Senha", type="password")
        confirma_pwd = st.text_input("Confirme a Nova Senha", type="password")
        
        if st.button("Validar e Alterar Senha", use_container_width=True):
            user_data = df_u[df_u['nome'] == user_reset].iloc[0]
            if str(user_code_input) == str(user_data['codigo']):
                if nova_pwd == confirma_pwd and nova_pwd != "":
                    idx = df_u[df_u['nome'] == user_reset].index[0] + 2
                    ws_usuarios.update_cell(idx, 2, nova_pwd)
                    st.cache_data.clear() # Limpa cache após alteração
                    st.success("✅ Senha alterada com sucesso!")
                else:
                    st.error("As novas senhas não coincidem.")
            else:
                st.error("❌ Código Único incorreto.")
    st.stop()

# =========================
# INTERFACE PRINCIPAL
# =========================
st.markdown(f"### {st.session_state.user}: **{st.session_state.role}**")

abas_disponiveis = ["Registrar Venda", "Histórico"]
if st.session_state.role == "ADM":
    abas_disponiveis.append("Gerenciar Produtos")

tabs = st.tabs(abas_disponiveis)

# --- ABA 1: REGISTRAR VENDA ---
with tabs[0]:
    st.subheader("🛒 Nova Venda")
    df_p = get_products_df()
    
    if df_p.empty:
        st.info("Nenhum produto disponível no momento.")
    else:
        # Seleção fora do form para atualizar o preço em tempo real
        prod_nome = st.selectbox("Selecione o Produto", df_p['produto'].tolist(), key="sel_produto")
        
        item_row = df_p[df_p['produto'] == prod_nome].iloc[0]
        preco_sugerido = float(item_row.get('preco', 0.0))
        custo_unitario = float(item_row.get('custo', 0.0))

        with st.form("form_venda", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                qtd = st.number_input("Quantidade", min_value=1, value=1, step=1)
                valor_total_venda = st.number_input(
                    "Valor Total da Venda (R$)", 
                    value=round(preco_sugerido * qtd, 2),
                    step=0.01,
                    format="%.2f"
                )
                
            with col2:
                data_v = st.date_input("Data", datetime.now())
                obs = st.text_input("Observação / Detalhes", placeholder="Ex: Cartão, Nome do cliente...")
            
            enviado = st.form_submit_button("✅ Confirmar Venda", use_container_width=True, type="primary")
            
            if enviado:
                custo_total = round(custo_unitario * qtd, 2)
                ws_vendas.append_row([
                    st.session_state.user,
                    data_v.strftime("%Y-%m-%d"),
                    float(valor_total_venda),
                    prod_nome,
                    f"{obs} (Qtd: {int(qtd)})",
                    data_v.strftime("%m/%Y"),
                    int(qtd),
                    custo_total
                ])
                st.cache_data.clear() # Limpa cache para atualizar o histórico
                st.success(f"Registrado com sucesso!")
                st.balloons()

# --- ABA 2: HISTÓRICO ---
with tabs[1]:
    st.subheader("📊 Relatório de Vendas")
    v_data = get_vendas_data()
    if v_data:
        v_df = pd.DataFrame(v_data)
        v_df.columns = [str(c).strip().lower() for c in v_df.columns]
        
        if st.session_state.role != "ADM":
            v_df = v_df[v_df['vendedor'] == st.session_state.user]
            if 'custo_total' in v_df.columns:
                v_df = v_df.drop(columns=['custo_total'])
        
        if not v_df.empty:
            meses = sorted(v_df['mes_referencia'].unique(), reverse=True)
            mes_f = st.selectbox("Selecione o Mês", meses)
            df_f = v_df[v_df['mes_referencia'] == mes_f].copy()
            
            st.dataframe(df_f, use_container_width=True)
            
            # Métricas
            col_m1, col_m2, col_m3 = st.columns(3)
            total_venda = pd.to_numeric(df_f['valor']).sum()
            col_m1.metric("Total Vendido", f"R$ {total_venda:,.2f}")
            
            if st.session_state.role == "ADM" and 'custo_total' in df_f.columns:
                total_custo = pd.to_numeric(df_f['custo_total']).sum()
                lucro = total_venda - total_custo
                col_m2.metric("Custo Total", f"R$ {total_custo:,.2f}")
                col_m3.metric("Lucro Total", f"R$ {lucro:,.2f}")
            
            st.divider()
            st.subheader("🗑️ Eliminar Registos")
            venda_idx = st.selectbox("Escolha uma venda para apagar", df_f.index)
            
            if st.button("Remover Permanentemente", type="secondary"):
                ws_vendas.delete_rows(int(venda_idx) + 2)
                st.cache_data.clear() # Força atualização após apagar
                st.warning("Registo removido!")
                st.rerun()
        else:
            st.info("Sem vendas registadas.")

# --- ABA 3: PRODUTOS (ADM) ---
if st.session_state.role == "ADM":
    with tabs[2]:
        st.subheader("🛠️ Gestão de Itens")
        c_add, c_edit = st.columns(2)
        
        with c_add:
            with st.expander("➕ Novo Produto", expanded=True):
                with st.form("novo_produto_form", clear_on_submit=True):
                    n_prod = st.text_input("Nome do Item")
                    n_prec = st.number_input("Preço de Venda", min_value=0.0, step=0.01)
                    n_custo = st.number_input("Custo Unitário", min_value=0.0, step=0.01)
                    if st.form_submit_button("Salvar"):
                        if n_prod:
                            ws_produtos.append_row([n_prod, n_prec, n_custo, "Ativo"])
                            st.cache_data.clear()
                            st.toast("Cadastrado!", icon='✅')
                            st.rerun()

        with c_edit:
            with st.expander("📝 Editar/Remover", expanded=True):
                df_prods_all = pd.DataFrame(ws_produtos.get_all_records())
                if not df_prods_all.empty:
                    df_prods_all.columns = [str(c).strip().lower() for c in df_prods_all.columns]
                    sel_p = st.selectbox("Produto a modificar", df_prods_all['produto'].tolist())
                    dados_p = df_prods_all[df_prods_all['produto'] == sel_p].iloc[0]
                    idx_p = df_prods_all[df_prods_all['produto'] == sel_p].index[0] + 2
                    
                    with st.form("form_edicao"):
                        edit_nome = st.text_input("Nome", value=dados_p['produto'])
                        edit_preco = st.number_input("Preço", value=float(dados_p['preco']), step=0.01)
                        edit_custo = st.number_input("Custo", value=float(dados_p['custo']), step=0.01)
                        
                        b1, b2, b3 = st.columns(3)
                        if b1.form_submit_button("💾 Salvar"):
                            ws_produtos.update_cell(idx_p, 1, edit_nome)
                            ws_produtos.update_cell(idx_p, 2, edit_preco)
                            ws_produtos.update_cell(idx_p, 3, edit_custo)
                            st.cache_data.clear()
                            st.rerun()
                        if b2.form_submit_button("👁️ Ocultar"):
                            ws_produtos.update_cell(idx_p, 4, "Oculto")
                            st.cache_data.clear()
                            st.rerun()
                        if b3.form_submit_button("🗑️ Apagar", type="primary"):
                            ws_produtos.delete_rows(idx_p)
                            st.cache_data.clear()
                            st.rerun()
                
st.sidebar.divider()
if st.sidebar.button("Sair do Sistema"):
    st.session_state.logged_in = False
    st.rerun()

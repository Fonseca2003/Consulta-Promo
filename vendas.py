import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# =========================
# CONEXÃO E FUNÇÕES BASE
# =========================
def connect_google_sheets():
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

sheet = connect_google_sheets()
ws_vendas = sheet.worksheet("vendas")
ws_usuarios = sheet.worksheet("usuarios")
ws_produtos = sheet.worksheet("produtos")

def get_users_df():
    df = pd.DataFrame(ws_usuarios.get_all_records())
    # Normaliza colunas para evitar erros de digitação na planilha
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def get_products_df():
    data = ws_produtos.get_all_records()
    if not data:
        return pd.DataFrame(columns=['produto', 'preco', 'status'])
    
    df = pd.DataFrame(data)
    # Normaliza colunas: Tirar espaços e colocar em minúsculo
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    if 'status' in df.columns:
        return df[df['status'] != 'Oculto']
    return df

# =========================
# SISTEMA DE LOGIN E SEGURANÇA
# =========================
        client = gspread.authorize(creds)
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
                    st.success("✅ Senha alterada com sucesso! Volte para a aba de Login.")
                else:
                    st.error("As novas senhas não coincidem.")
            else:
                st.error("❌ Código Único incorreto.")
    st.stop()

# =========================
# INTERFACE PRINCIPAL
# =========================
st.markdown(f"### 👤 {st.session_state.user}: **{st.session_state.role}**")

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
        with st.form("form_venda", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                # Agora usamos 'produto' (minúsculo) garantido pela função get_products_df
                prod_nome = st.selectbox("Produto", df_p['produto'].tolist())
                
                # Preço sugerido
                item_data = df_p[df_p['produto'] == prod_nome].iloc[0]
                p_sugerido = float(item_data['preco'])
                
                valor_venda = st.number_input("Valor da Venda (R$)", value=p_sugerido, step=0.01)
            with col2:
                data_v = st.date_input("Data", datetime.now())
                obs = st.text_input("Observação / Detalhes")
                
            # O botão de envio DEVE estar dentro do 'with st.form'
            enviado = st.form_submit_button("Confirmar Registro", use_container_width=True)
            
            if enviado:
                ws_vendas.append_row([
                    st.session_state.user, 
                    data_v.strftime("%Y-%m-%d"), 
                    valor_venda, 
                    prod_nome, 
                    obs,
                    data_v.strftime("%m/%Y")
                ])
                st.success("Venda salva com sucesso!")
                st.rerun()

# --- ABA 2: HISTÓRICO ---
with tabs[1]:
    st.subheader("📊 Relatório de Vendas")
    v_data = ws_vendas.get_all_records()
    if v_data:
        v_df = pd.DataFrame(v_data)
        v_df.columns = [str(c).strip().lower() for c in v_df.columns] # Normaliza colunas
        
        if st.session_state.role != "ADM":
            v_df = v_df[v_df['vendedor'] == st.session_state.user]
        
        if not v_df.empty:
            meses = sorted(v_df['mes_referencia'].unique(), reverse=True)
            mes_f = st.selectbox("Selecione o Mês", meses)
            df_f = v_df[v_df['mes_referencia'] == mes_f]
            
            st.dataframe(df_f, use_container_width=True)
            st.metric("Total Vendido", f"R$ {df_f['valor'].sum():,.2f}")
            
            st.divider()
            st.subheader("🗑️ Gerenciar Registros")
            venda_idx = st.selectbox("Selecione uma venda para remover", 
                                     df_f.index, 
                                     format_func=lambda x: f"ID {x} - {df_f.loc[x, 'produto']} (R$ {df_f.loc[x, 'valor']})")
            
            if st.button("Excluir Registro Permanente"):
                ws_vendas.delete_rows(int(venda_idx) + 2)
                st.warning("Registro removido!")
                st.rerun()
        else:
            st.info("Nenhuma venda registrada para seu usuário.")
    else:
        st.info("A planilha de vendas está vazia.")

# --- ABA 3: PRODUTOS (ADM) ---
if st.session_state.role == "ADM":
    with tabs[2]:
        st.subheader("🛠️ Gestão de Itens e Preços")
        c_add, c_edit = st.columns(2)
        
        with c_add:
            with st.expander("➕ Cadastrar Novo Produto", expanded=True):
                n_prod = st.text_input("Nome do Item")
                n_prec = st.number_input("Preço Base", min_value=0.0, step=0.1)
                if st.button("Adicionar à Lista"):
                    if n_prod:
                        ws_produtos.append_row([n_prod, n_prec, "Ativo"])
                        st.success("Produto Adicionado!")
                        st.rerun()
                    else:
                        st.error("Digite um nome.")

        with c_edit:
            with st.expander("📝 Editar/Ocultar", expanded=True):
                df_prods_all = pd.DataFrame(ws_produtos.get_all_records())
                if not df_prods_all.empty:
                    df_prods_all.columns = [str(c).strip().lower() for c in df_prods_all.columns]
                    sel_p = st.selectbox("Escolher Produto", df_prods_all['produto'].tolist())
                    idx_p = df_prods_all[df_prods_all['produto'] == sel_p].index[0] + 2
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("Ocultar Item"):
                        ws_produtos.update_cell(idx_p, 3, "Oculto")
                        st.rerun()
                    if c_btn2.button("Apagar", type="primary"):
                        ws_produtos.delete_rows(idx_p)
                        st.rerun()

st.sidebar.divider()
if st.sidebar.button("Sair do Sistema"):
    st.session_state.logged_in = False
    st.rerun()

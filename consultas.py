import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import glob

# =========================
# CONFIGURAÇÕES
# =========================

URL_LOGIN = "http://10.110.96.44:8000/login"

XPATH_USUARIO = "/html/body/div/div[1]/div/form/div[1]/input"
XPATH_SENHA = "/html/body/div/div[1]/div/form/div[2]/input"
XPATH_BOTAO_LOGIN = "/html/body/div/div[1]/div/form/button"

XPATH_CAMPO_QUERY = "/html/body/div[1]/form/div[1]/div/div/div[1]/div[2]/div[1]/div[4]"
XPATH_BOTAO_EXECUTAR = "/html/body/div[1]/form/div[2]/button"
XPATH_BOTAO_DOWNLOAD = "/html/body/div[2]/div[2]/div[2]/div[1]/div/form/button"

ID_MSG_ERRO = "error-message"
ID_SECAO_ERRO = "error-section"

# =========================
# MONTAR QUERY
# =========================

def montar_query(promocao, empresa, produto):
    query = f"""
SELECT DISTINCT 
       A.SEQPRODUTO AS produto,                         
       E.DESCCOMPLETA,
       A.QTDEMBALAGEM,
       A.NROEMPRESA,
       'AUTO SERVIÇO' AS segmento,
       TO_CHAR(B.DTAINICIO, 'DD/MM/YYYY HH24:MI:SS') AS datainicio,
       TO_CHAR(B.DTAFIM, 'DD/MM/YYYY HH24:MI:SS') AS datafim, 
       B.PROMOCAO,
       A.PRECOPROMOCIONAL,
       C.PRECOVALIDPROMOC,
       A.DTAINCLUSAO
FROM consinco.MRL_PROMOCAOITEM A
INNER JOIN consinco.MRL_PROMOCAO B 
     ON B.NROEMPRESA = A.NROEMPRESA
    AND B.SEQPROMOCAO = A.SEQPROMOCAO
    AND B.CENTRALLOJA = A.CENTRALLOJA
    AND B.NROSEGMENTO = A.NROSEGMENTO
INNER JOIN consinco.MRL_PRODEMPSEG C 
     ON A.SEQPRODUTO = C.SEQPRODUTO
    AND B.NROSEGMENTO = C.NROSEGMENTO
    AND B.NROEMPRESA = C.NROEMPRESA
    AND A.QTDEMBALAGEM = C.QTDEMBALAGEM
INNER JOIN consinco.MAP_PRODUTO E 
     ON E.SEQPRODUTO = A.SEQPRODUTO
INNER JOIN consinco.MRL_PRODUTOEMPRESA G 
     ON G.NROEMPRESA = A.NROEMPRESA 
    AND G.SEQPRODUTO = A.SEQPRODUTO
    AND B.PROMOCAO = '{promocao}'
WHERE B.NROSEGMENTO = 2
"""
    if empresa:
        query += f"\nAND G.NROEMPRESA = {empresa}"
    if produto:
        query += f"\nAND G.SEQPRODUTO = {produto}"
    return query

# =========================
# DOWNLOAD
# =========================

def esperar_download_concluir(diretorio, timeout=120):
    segundos = 0
    while segundos < timeout:
        time.sleep(1)
        temp = glob.glob(os.path.join(diretorio, "*.crdownload")) + glob.glob(os.path.join(diretorio, "*.tmp"))
        if not temp:
            arquivos = sorted(glob.glob(os.path.join(diretorio, "*.xlsx")), key=os.path.getctime, reverse=True)
            if arquivos:
                return f"✅ Sucesso: {os.path.basename(arquivos[0])}"
        segundos += 1
    return "⚠️ Tempo esgotado aguardando o arquivo .xlsx"

# =========================
# EXECUÇÃO SELENIUM - USANDO chromedriver DO SISTEMA
# =========================

def executar_automacao(usuario, senha, query):
    download_dir = os.getcwd()
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--remote-debugging-port=9222")
    
    # Usa o Chromium instalado via packages.txt
    options.binary_location = "/usr/bin/chromium"

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "browser.helperApps.neverAsk.saveToDisk": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream"
    }
    options.add_experimental_option("prefs", prefs)

    try:
        # Usa o chromedriver instalado pelo sistema (chromium-driver)
        service = Service("/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 240)

        driver.get(URL_LOGIN)
        wait.until(EC.presence_of_element_located((By.XPATH, XPATH_USUARIO))).send_keys(usuario)
        driver.find_element(By.XPATH, XPATH_SENHA).send_keys(senha)
        driver.find_element(By.XPATH, XPATH_BOTAO_LOGIN).click()

        campo = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_CAMPO_QUERY)))
        ActionChains(driver).click(campo)\
            .key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL)\
            .send_keys(Keys.BACKSPACE).send_keys(query).perform()

        driver.find_element(By.XPATH, XPATH_BOTAO_EXECUTAR).click()

        while "/results/" not in driver.current_url:
            if driver.find_elements(By.ID, ID_SECAO_ERRO):
                msg = driver.find_element(By.ID, ID_MSG_ERRO).text
                driver.quit()
                return f"❌ Erro no servidor: {msg}"
            time.sleep(2)

        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": download_dir})
        botao = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_DOWNLOAD)))
        botao.click()
        time.sleep(4)

        resultado = esperar_download_concluir(download_dir)
        driver.quit()
        return resultado

    except Exception as e:
        return f"❌ Erro na automação: {str(e)}"

# =========================
# INTERFACE STREAMLIT
# =========================

st.set_page_config(page_title="Consulta Promoção", layout="wide")
st.title("🔎 Consulta Promoção")

with st.form("form_consulta"):
    col1, col2 = st.columns(2)
    with col1:
        usuario = st.text_input("Usuário", placeholder="Usuário Consinco")
    with col2:
        senha = st.text_input("Senha", type="password")

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        promocao = st.text_input("Nome da Promoção (Obrigatório)")
    with col_b:
        empresa = st.text_input("Loja (Opcional)")
    with col_c:
        produto = st.text_input("Produto (Opcional)")

    st.markdown("<br>", unsafe_allow_html=True)
    executar = st.form_submit_button("🚀 Executar Consulta", use_container_width=True)

if executar:
    if not usuario or not senha or not promocao:
        st.error("⚠️ Preencha Usuário, Senha e Nome da Promoção.")
    else:
        sql = montar_query(promocao, empresa, produto)
        
        with st.expander("📄 SQL Gerado"):
            st.code(sql, language="sql")

        with st.spinner("Executando no SGE e baixando arquivo... (pode demorar até 2 minutos)"):
            resultado = executar_automacao(usuario, senha, sql)

        if resultado.startswith("✅"):
            st.success(resultado)
        elif resultado.startswith("⚠️"):
            st.warning(resultado)
        else:
            st.error(resultado)

st.caption("Inteligência Comercial Mart Minas")

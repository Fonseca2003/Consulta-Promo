import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import glob

# =========================
# CONFIGURAÇÕES E XPATHS
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
# LÓGICA DA QUERY (mantida igual)
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
# FUNÇÃO DE DOWNLOAD (melhorada)
# =========================

def esperar_download_concluir(diretorio, timeout=90):
    segundos = 0
    while segundos < timeout:
        time.sleep(1)
        arquivos_temp = glob.glob(os.path.join(diretorio, "*.crdownload")) + glob.glob(os.path.join(diretorio, "*.tmp"))
        if not arquivos_temp:
            arquivos_xlsx = sorted(glob.glob(os.path.join(diretorio, "*.xlsx")), key=os.path.getctime, reverse=True)
            if arquivos_xlsx:
                return f"Sucesso: Download concluído → {os.path.basename(arquivos_xlsx[0])}"
        segundos += 1
    return "Aviso: Tempo esgotado aguardando o arquivo .xlsx"

# =========================
# AUTOMAÇÃO SELENIUM
# =========================

def executar_automacao(usuario, senha, query):
    download_dir = os.getcwd()
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    
    # Preferências para download
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "browser.helperApps.neverAsk.saveToDisk": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream"
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Usa webdriver_manager para evitar problemas de versão do chromedriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 300)

    try:
        driver.get(URL_LOGIN)
        wait.until(EC.presence_of_element_located((By.XPATH, XPATH_USUARIO))).send_keys(usuario)
        driver.find_element(By.XPATH, XPATH_SENHA).send_keys(senha)
        driver.find_element(By.XPATH, XPATH_BOTAO_LOGIN).click()

        campo_query = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_CAMPO_QUERY)))
        actions = ActionChains(driver)
        actions.click(campo_query)\
               .key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL)\
               .send_keys(Keys.BACKSPACE)\
               .send_keys(query)\
               .perform()

        driver.find_element(By.XPATH, XPATH_BOTAO_EXECUTAR).click()

        # Aguarda página de resultados
        while True:
            if "/results/" in driver.current_url:
                break
            if driver.find_elements(By.ID, ID_SECAO_ERRO) and driver.find_element(By.ID, ID_SECAO_ERRO).is_displayed():
                msg = driver.find_element(By.ID, ID_MSG_ERRO).text
                return f"Erro no Servidor: {msg}"
            time.sleep(2)

        # Força comportamento de download
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": download_dir})

        botao_download = wait.until(EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_DOWNLOAD)))
        botao_download.click()
        time.sleep(3)

        return esperar_download_concluir(download_dir, timeout=90)

    except Exception as e:
        return f"Erro na automação: {str(e)}"
    finally:
        driver.quit()

# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="SGE - Consulta Promoção", layout="wide")
st.title("Consulta Promoção")

with st.form("form_consulta"):
    c1, c2 = st.columns(2)
    with c1:
        user_input = st.text_input("Usuário", placeholder="Usuário Consinco")
    with c2:
        pass_input = st.text_input("Senha", type="password", placeholder="Senha")

    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        promocao_input = st.text_input("Nome da Promoção (Obrigatório)")
    with f2:
        empresa_input = st.text_input("Loja (Opcional)")
    with f3:
        produto_input = st.text_input("Produto (Opcional)")

    st.markdown("<br>", unsafe_allow_html=True)
    btn_executar = st.form_submit_button("🚀 Executar", use_container_width=True)

if btn_executar:
    if not user_input or not pass_input or not promocao_input:
        st.error("⚠️ Por favor, preencha o usuário, senha e o nome da promoção.")
    else:
        sql_final = montar_query(promocao_input, empresa_input, produto_input)
        
        with st.expander("Visualizar SQL Gerado"):
            st.code(sql_final, language="sql")

        with st.spinner("Executando consulta e baixando arquivo..."):
            resultado_final = executar_automacao(user_input, pass_input, sql_final)

        if "Sucesso" in resultado_final:
            st.success(resultado_final)
        elif "Aviso" in resultado_final:
            st.warning(resultado_final)
        else:
            st.error(resultado_final)

st.caption("Inteligência Comercial Mart Minas")

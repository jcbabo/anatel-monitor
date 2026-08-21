"""Monitor de agenda da Anatel (SEC).

Conecta-se a um Chrome/Edge JÁ ABERTO (via porta de depuracao remota),
atualiza periodicamente a aba da tela de inscricao e avisa quando
aparecer agenda disponivel.

Uso:
    python monitor.py
    python monitor.py --min 30 --max 50 --alerta-js
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import UnexpectedAlertPresentException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL_ALVO = "https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp"

# Frases que indicam que NAO ha agenda. Se todas sumirem, avisamos.
# Escreva SEM acento e em minusculas: a comparacao usa o texto normalizado.
PADROES_SEM_AGENDA = [
    "nao ha agenda",
    "nao existe agenda",
    "nenhuma agenda",
    "sem agenda",
    "nao ha vagas",
    "nao existem vagas",
    "sem vagas",
    "nao ha datas",
    "nenhum resultado",
]

# Secao da pagina onde a agenda aparece; serve para confirmar que a
# sessao continua valida e a tela certa foi carregada.
MARCADOR_TELA = "relacao de prova"

# Frases que indicam agenda disponivel.
PADROES_COM_AGENDA = [
    "agenda disponivel",
    "agendas disponiveis",
    "vagas disponiveis",
    "selecione a data",
    "escolha a data",
    "data da prova",
]


def normalizar(texto: str) -> str:
    """Minusculas, sem acento e com espacos colapsados."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()

def agora() -> str:
    return datetime.now().strftime("%d/%m %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{agora()}] {msg}", flush=True)

def detectar_versao(host: str, porta: int) -> str | None:
    """Le a versao major do Chrome remoto para casar com o chromedriver."""
    try:
        with urllib.request.urlopen(
            f"http://{host}:{porta}/json/version", timeout=5
        ) as resp:
            dados = json.load(resp)
    except (OSError, ValueError):
        return None
    match = re.search(r"Chrome/(\d+)", dados.get("Browser", ""))
    return match.group(1) if match else None


def conectar(host: str, porta: int) -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"{host}:{porta}")
    versao = detectar_versao(host, porta)
    if versao:
        options.browser_version = versao
    return webdriver.Chrome(options=options)


def selecionar_aba(driver: webdriver.Chrome, fragmento_url: str) -> None:
    """Coloca o foco na aba cuja URL contem o fragmento informado."""
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if fragmento_url.lower() in driver.current_url.lower():
            return
    raise RuntimeError(
        f"Nenhuma aba aberta com a URL contendo '{fragmento_url}'. "
        "Abra a pagina no navegador antes de rodar o monitor."
    )


def coletar_estado(driver: webdriver.Chrome) -> tuple[str, list[str]]:
    """Retorna (texto normalizado da pagina, datas visiveis no corpo)."""
    corpo = driver.find_element(By.TAG_NAME, "body").text
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", corpo)
    return normalizar(corpo), datas


def tem_agenda(texto: str, datas: list[str]) -> tuple[bool, str]:
    if MARCADOR_TELA not in texto:
        return False, "tela inesperada (sessao expirada ou pagina de erro?)"
    if any(p in texto for p in PADROES_SEM_AGENDA):
        return False, "pagina informa que nao ha agendas disponiveis"
    if datas:
        return True, f"datas na tela: {', '.join(sorted(set(datas))[:10])}"
    for padrao in PADROES_COM_AGENDA:
        if padrao in texto:
            return True, f"texto encontrado: '{padrao}'"
    return True, "a mensagem de 'nao ha agendas' desapareceu da tela"


def alertar_no_navegador(driver: webdriver.Chrome, mensagem: str,
                         usar_alert: bool) -> None:
    """Mostra o aviso dentro da propria aba do navegador."""
    texto = json.dumps(mensagem)
    if usar_alert:
        # setTimeout evita que o execute_script fique preso esperando o OK.
        script = f"setTimeout(function(){{ window.alert({texto}); }}, 0);"
    else:
        script = f"""
        document.title = '>>> AGENDA DISPONIVEL <<<';
        var d = document.getElementById('__monitor_anatel__') ||
                document.createElement('div');
        d.id = '__monitor_anatel__';
        d.textContent = {texto};
        d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;'
            + 'background:#c00;color:#fff;font:bold 18px sans-serif;padding:16px;'
            + 'text-align:center;white-space:pre-wrap';
        document.body.appendChild(d);
        """
    try:
        driver.execute_script(script)
    except (WebDriverException, UnexpectedAlertPresentException) as exc:
        log(f"Nao consegui exibir o aviso no navegador: {exc}")


def alertar(mensagem: str) -> None:
    # Bipe do terminal (varias vezes para chamar atencao)
    for _ in range(5):
        sys.stdout.write("\a")
        sys.stdout.flush()
        time.sleep(0.3)

    # Notificacao no Windows a partir do WSL
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if powershell:
        script = (
            "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')"
            " > $null; "
            "[System.Windows.Forms.MessageBox]::Show("
            f"'{mensagem}', 'AGENDA ANATEL DISPONIVEL')"
        )
        try:
            subprocess.Popen(
                [powershell, "-NoProfile", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass

    notify = shutil.which("notify-send")
    if notify:
        try:
            subprocess.Popen([notify, "AGENDA ANATEL DISPONIVEL", mensagem])
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor de agenda Anatel/SEC")
    parser.add_argument("--host", default="localhost",
                        help="host do navegador (ex.: IP do Windows visto do WSL)")
    parser.add_argument("--porta", type=int, default=9222,
                        help="porta de depuracao remota do navegador")
    parser.add_argument("--min", dest="minimo", type=float, default=30.0,
                        help="intervalo minimo entre refreshes (padrao: 30s)")
    parser.add_argument("--max", dest="maximo", type=float, default=50.0,
                        help="intervalo maximo entre refreshes (padrao: 50s)")
    parser.add_argument("--url", default=URL_ALVO,
                        help="fragmento da URL da aba a monitorar")
    parser.add_argument("--alerta-js", action="store_true",
                        help="usa window.alert() na aba (bloqueia ate clicar OK)")
    parser.add_argument("--sem-refresh", action="store_true",
                        help="so inspeciona a pagina, sem dar F5 (util com captcha)")
    parser.add_argument("--parar-ao-achar", action="store_true",
                        help="encerra o monitor no primeiro alerta")
    args = parser.parse_args()

    if args.minimo > args.maximo:
        parser.error("--min nao pode ser maior que --max")

    try:
        driver = conectar(args.host, args.porta)
    except WebDriverException as exc:
        log(f"Nao consegui conectar em {args.host}:{args.porta}. Detalhe: {exc.msg}")
        log("Abra o Chrome com --remote-debugging-port=9222 e confira o --host.")
        return 1

    try:
        selecionar_aba(driver, args.url)
    except (RuntimeError, WebDriverException) as exc:
        log(str(exc))
        return 1

    log(f"Monitorando {driver.current_url}")
    log(f"Refresh a cada {args.minimo:.0f}-{args.maximo:.0f}s (aleatorio). "
        "Ctrl+C para parar.")

    tentativa = 0
    while True:
        tentativa += 1
        try:
            if not args.sem_refresh:
                driver.refresh()
                time.sleep(3)  # deixa a pagina ASP terminar de renderizar
            texto, datas = coletar_estado(driver)
            achou, motivo = tem_agenda(texto, datas)
            if achou:
                log(f"*** POSSIVEL AGENDA DISPONIVEL *** ({motivo})")
                mensagem = f"Agenda disponivel na Anatel!\n{motivo}"
                alertar_no_navegador(driver, mensagem, args.alerta_js)
                alertar(mensagem)
                if args.parar_ao_achar or args.alerta_js:
                    # Com window.alert aberto o Selenium nao consegue continuar.
                    log("Monitor encerrado: confira a aba do navegador.")
                    return 0
            else:
                log(f"tentativa {tentativa}: nada ainda ({motivo})")
        except WebDriverException as exc:
            log(f"Erro no navegador: {exc.msg}. Tentando reconectar na aba...")
            try:
                selecionar_aba(driver, args.url)
            except (RuntimeError, WebDriverException):
                log("Aba perdida. Reabra a pagina e rode o monitor novamente.")
                return 1
        espera = random.uniform(args.minimo, args.maximo)
        log(f"proximo refresh em {espera:.1f}s")
        time.sleep(espera)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Monitor encerrado pelo usuario.")

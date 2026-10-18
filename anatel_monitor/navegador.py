"""Conexao com o Chrome/Edge remoto e localizacao de abas."""

from __future__ import annotations

import json
import re
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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


def selecionar_aba(driver: webdriver.Chrome, fragmento_url: str) -> str:
    """Coloca o foco na aba cuja URL contem o fragmento e devolve seu handle."""
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if fragmento_url.lower() in driver.current_url.lower():
            return handle
    raise RuntimeError(
        f"Nenhuma aba aberta com a URL contendo '{fragmento_url}'. "
        "Abra a pagina no navegador antes de rodar o monitor."
    )

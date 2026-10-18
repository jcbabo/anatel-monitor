"""Normalizacao de texto e regras de deteccao de agenda disponivel."""

from __future__ import annotations

import re
import unicodedata

from selenium import webdriver
from selenium.webdriver.common.by import By

from .config import MARCADOR_TELA, PADROES_COM_AGENDA, PADROES_SEM_AGENDA


def normalizar(texto: str) -> str:
    """Minusculas, sem acento e com espacos colapsados."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


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

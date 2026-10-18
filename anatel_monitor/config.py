"""Constantes de URLs monitoradas e padroes de texto usados na deteccao."""

from __future__ import annotations

URL_ALVO = "https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp"

# Aba de login/SSO que precisa ser mantida viva para a sessao nao expirar.
URL_SESSAO = "https://apps.anatel.gov.br/acesso/"

# Frases que indicam que NAO ha agenda. Se todas sumirem, avisamos.
# Escrever SEM acento e em minusculas: a comparacao usa o texto normalizado.
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

# serve para confirmar que a sessao continua valida e a tela certa foi
# carregada.
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

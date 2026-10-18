"""Monitor de agenda da Anatel (SEC).

Conecta-se a um Chrome/Edge JÁ ABERTO (via porta de depuracao remota),
atualiza periodicamente a aba da tela de inscricao e avisa quando
aparecer agenda disponivel. Inicialmente está configurado para fazer uma requisição por minuto.

Uso:
    python monitor.py
    python monitor.py --alerta-js
    python monitor.py --min 45 --max 60 --alerta-js
"""

from __future__ import annotations

import argparse
import random
import sys
import time

from selenium.common.exceptions import WebDriverException

from anatel_monitor.alertas import alertar, alertar_no_navegador
from anatel_monitor.config import URL_ALVO, URL_SESSAO
from anatel_monitor.deteccao import coletar_estado, tem_agenda
from anatel_monitor.navegador import conectar, selecionar_aba
from anatel_monitor.util import log


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor de agenda Anatel/SEC")
    parser.add_argument("--host", default="localhost",
                        help="host do navegador (ex.: IP do Windows visto do WSL)")
    parser.add_argument("--porta", type=int, default=9222,
                        help="porta de depuracao remota do navegador")
    parser.add_argument("--min", dest="minimo", type=float, default=45.0,
                        help="intervalo minimo entre refreshes (padrao: 45s)")
    parser.add_argument("--max", dest="maximo", type=float, default=60.0,
                        help="intervalo maximo entre refreshes (padrao: 60s  )")
    parser.add_argument("--url", default=URL_ALVO,
                        help="fragmento da URL da aba a monitorar")
    parser.add_argument("--url-sessao", default=URL_SESSAO,
                        help="fragmento da URL da aba de login/sessao a manter viva")
    parser.add_argument("--sem-aba-sessao", action="store_true",
                        help="desativa o refresh da aba de sessao")
    parser.add_argument("--alerta-js", action="store_true",
                        help="usa window.alert() na aba (bloqueia ate clicar OK)")
    parser.add_argument("--sem-refresh", action="store_true",
                        help="so inspeciona a pagina, sem dar F5 (util com captcha)")
    parser.add_argument("--parar-ao-achar", action="store_true",
                        help="encerra o monitor por completo no primeiro alerta"
                            "(por padrao ele continua rodando so para manter a sessao viva)")
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
        handle_agenda = selecionar_aba(driver, args.url)
    except (RuntimeError, WebDriverException) as exc:
        log(str(exc))
        return 1

    handle_sessao: str | None = None
    if not args.sem_aba_sessao:
        try:
            handle_sessao = selecionar_aba(driver, args.url_sessao)
        except (RuntimeError, WebDriverException) as exc:
            log(f"Aviso: {exc} A aba de sessao nao sera atualizada.")

    driver.switch_to.window(handle_agenda)
    log(f"Monitorando {driver.current_url}")
    if handle_sessao:
        log("Aba de sessao encontrada: sera atualizada junto para evitar timeout.")
    log(f"Refresh a cada {args.minimo:.0f}-{args.maximo:.0f}s (aleatorio). "
        "Ctrl+C para parar.")

    tentativa = 0
    agenda_encontrada = False
    while True:
        tentativa += 1
        if not agenda_encontrada:
            try:
                driver.switch_to.window(handle_agenda)
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
                    agenda_encontrada = True
                    if args.parar_ao_achar:
                        log("Monitor encerrado: confira a aba do navegador.")
                        return 0
                    log("Refresh da aba de agenda pausado. "
                        "A aba de sessao continua sendo atualizada.")
                else:
                    log(f"tentativa {tentativa}: nada ainda ({motivo})")
            except WebDriverException as exc:
                log(f"Erro no navegador: {exc.msg}. Tentando reconectar na aba...")
                try:
                    handle_agenda = selecionar_aba(driver, args.url)
                except (RuntimeError, WebDriverException):
                    log("Aba perdida. Reabra a pagina e rode o monitor novamente.")
                    return 1

        if handle_sessao:
            try:
                driver.switch_to.window(handle_sessao)
                driver.refresh()
            except WebDriverException as exc:
                log(f"Erro ao atualizar a aba de sessao: {exc.msg}. "
                    "Tentando reconectar...")
                try:
                    handle_sessao = selecionar_aba(driver, args.url_sessao)
                except (RuntimeError, WebDriverException):
                    log("Aba de sessao perdida; nao sera mais atualizada.")
                    handle_sessao = None

        espera = random.uniform(args.minimo, args.maximo)
        log(f"proximo refresh em {espera:.1f}s")
        time.sleep(espera)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Monitor encerrado pelo usuario.")

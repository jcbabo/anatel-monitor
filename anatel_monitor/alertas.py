"""Disparo de avisos: no navegador, no terminal e no sistema operacional."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import UnexpectedAlertPresentException, WebDriverException

from .util import log


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

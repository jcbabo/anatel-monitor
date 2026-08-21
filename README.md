# Monitor de Agenda da Anatel para marcação da prova de radioamador (SEC)

Script em Python que fica **atualizando (F5) automaticamente** a tela de inscrição
do SEC (Sistema de Emissão de Certificado de Radioperador) da Anatel e **avisa
assim que aparecer agenda disponível** para a prova.

O script **não abre um navegador novo e não faz login**. Ele se acopla a uma aba
que **você já deixou aberta e logada** no seu Chrome, usando o protocolo de
depuração remota (CDP). Isso é importante porque a página exige login e hCaptcha —
tudo isso continua sendo feito por você, manualmente, uma única vez.

- **Página monitorada:** `https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp`
- **Sinal de "sem vaga":** a frase `Não há agendas disponíveis no momento.` na seção *Relação de Prova*
- **Sinal de "tem vaga":** aquela frase sumir, ou aparecerem datas `dd/mm/aaaa` na tela

---

## Índice

1. [Requisitos](#1-requisitos)
2. [Instalação](#2-instalação)
3. [Preparando o Chrome](#3-preparando-o-chrome)
4. [Conectividade WSL → Windows](#4-conectividade-wsl--windows)
5. [Como rodar](#5-como-rodar)
6. [Opções de linha de comando](#6-opções-de-linha-de-comando)
7. [Como os alertas funcionam](#7-como-os-alertas-funcionam)
8. [Como a detecção funciona](#8-como-a-detecção-funciona)
9. [Solução de problemas](#9-solução-de-problemas)
10. [Estrutura do projeto](#10-estrutura-do-projeto)
11. [Boas práticas e limitações](#11-boas-práticas-e-limitações)

---

## 1. Requisitos

### Versões usadas e testadas

| Item | Versão testada | Observação |
| --- | --- | --- |
| Python | **3.12.3** | Mínimo **3.10** (o código usa `str \| None`, sintaxe de união de tipos do PEP 604) |
| Selenium | **4.47.0** | Mínimo **4.20** (versões 4.6+ trazem o Selenium Manager, que baixa o ChromeDriver sozinho) |
| Google Chrome | **151.0.7922.170** (Windows) | Qualquer versão recente serve; o script detecta a versão automaticamente |
| Sistema | Ubuntu no **WSL2** (kernel 6.18) | Funciona também em Linux nativo ou direto no Windows |

### Por que só Chrome (ou Edge)?

O script precisa se conectar a um navegador **já aberto**. Isso só é possível pelo
protocolo de depuração remota do Chromium (`--remote-debugging-port`).
O **Firefox não é suportado**: o Selenium não consegue se anexar a uma sessão do
Firefox que já está rodando — ele só sabe iniciar uma instância nova e limpa, o que
faria você perder o login. O Microsoft Edge funciona, pois também é Chromium.

### O que **não** é necessário

- **Não** precisa baixar o ChromeDriver na mão. O Selenium Manager (embutido no
  Selenium 4.6+) faz o download da versão correta e guarda em cache
  (`~/.cache/selenium`).
- **Não** precisa instalar Chrome dentro do WSL. O Chrome usado é o do Windows.

---

## 2. Instalação

Dentro do WSL, na pasta do projeto:

```bash
cd ~/jbabo/projects/anatel-monitor

# cria o ambiente virtual (isola as dependências do Python do sistema)
python3 -m venv .venv

# ativa o ambiente
source .venv/bin/activate

# instala as dependências
pip install -r requirements.txt
```

O arquivo [requirements.txt](requirements.txt) tem uma única dependência:

```
Selenium>=4.20
```

Para conferir se deu tudo certo:

```bash
python -V              # deve mostrar 3.10 ou superior
pip show selenium      # deve mostrar 4.20 ou superior
```

> **Dica:** se preferir não ativar o venv toda vez, pode chamar o interpretador
> direto: `.venv/bin/python monitor.py`. É o formato usado no restante deste README.

---

## 3. Preparando o Chrome

Esta é a parte que mais gera dúvida, então vai bem detalhada.

### 3.1. Abrir o Chrome com a porta de depuração

No **Windows** (PowerShell ou o próprio menu Executar), com o Chrome
**totalmente fechado**:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

A flag `--remote-debugging-port=9222` faz o Chrome abrir um servidor local na
porta 9222, por onde o Selenium vai conversar com ele.

#### Como descobrir o caminho do `chrome.exe`

O caminho acima é o mais comum, mas o Chrome também pode estar instalado só para
o seu usuário. Use uma destas formas para confirmar:

**Sem comando nenhum:** abra `chrome://version` no navegador e veja o campo
**"Caminho do executável"**.

**No PowerShell (Windows)** — pelo processo que já está rodando:

```powershell
Get-Process chrome | Select-Object -First 1 -ExpandProperty Path
```

Ou pelo registro (o Chrome pode estar registrado por máquina **ou** por usuário):

```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe').'(Default)'
(Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe').'(Default)'
```

**No WSL** — procurando direto nos caminhos montados em `/mnt/c`:

```bash
ls -1 "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
      "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
      /mnt/c/Users/*/AppData/Local/Google/Chrome/Application/chrome.exe 2>/dev/null
```

Lembre que, no comando do PowerShell, o caminho é escrito no formato do Windows
(`C:\Program Files\...`), e não no formato `/mnt/c/...` do WSL.

**Atenção:** se já houver qualquer janela do Chrome aberta, o comando acima apenas
abre uma aba nova na instância existente e **a flag é ignorada**. Feche tudo antes
(confira no Gerenciador de Tarefas se sobrou algum `chrome.exe`), ou use um perfil
separado:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
```

O `--user-data-dir` cria um perfil novo e independente, o que garante que a flag
seja aplicada mesmo com outro Chrome aberto. A desvantagem é que esse perfil não
tem suas extensões nem seus logins salvos — você vai precisar fazer o login do SEC
nessa janela.

### 3.2. Fazer login e deixar a aba certa aberta

Nessa janela do Chrome:

1. Acesse `https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp`
2. Faça o login normalmente e resolva o **hCaptcha** (isso é feito uma única vez —
   o F5 automático não pede o captcha de novo, isso foi testado).
3. Navegue até a tela de **Inscrição (Incluir)**, onde aparece a seção
   *Relação de Prova*.
4. **Deixe essa aba aberta.** Você pode usar outras abas e até minimizar a janela;
   o script troca o foco para a aba correta sozinho quando precisa.

### 3.3. Confirmar que está tudo pronto

De volta ao WSL:

```bash
# 1) o Chrome está escutando na porta de depuração?
curl -s http://localhost:9222/json/version
```

Resposta esperada (o campo `Browser` mostra a versão do Chrome):

```json
{
   "Browser": "Chrome/151.0.7922.170",
   "Protocol-Version": "1.3",
   ...
}
```

```bash
# 2) a aba do SEC está aberta?
curl -s http://localhost:9222/json/list | grep -o '"url": "[^"]*anatel[^"]*"'
```

Você deve ver a linha com `.../SEC/Inscricao/Incluir/Tela.asp`. Também vão aparecer
duas URLs do `hcaptcha.com` — isso é **normal**, os iframes do captcha ficam
carregados o tempo todo na página, mesmo depois de você já estar logado.

### 3.4. Usuários de WSL: confira a interoperabilidade com o Windows

O alerta por **caixa de mensagem do Windows** depende de o WSL conseguir executar
programas do Windows (a chamada *interop*). Teste assim:

```bash
powershell.exe -NoProfile -Command "'interop ok'"
```

Se aparecer `interop ok`, está tudo certo. Se aparecer algo como:

```
/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe: cannot execute binary file: Exec format error
```

a interoperabilidade está **desativada**. Confirme com:

```bash
cat /proc/sys/fs/binfmt_misc/WSLInterop
```

Se o arquivo não existir, crie (ou edite) o `/etc/wsl.conf` dentro do WSL:

```ini
[interop]
enabled = true
appendWindowsPath = true
```

E reinicie o WSL pelo PowerShell do Windows:

```powershell
wsl --shutdown
```

> **Importante:** o monitor **continua funcionando** sem o interop — o script trata
> a falha e simplesmente pula esse alerta. Você só perde a caixa de mensagem do
> Windows; o bipe, o `notify-send` e o aviso dentro da própria aba (faixa vermelha
> ou `window.alert()`) seguem normais. Como o aviso na aba é o mais confiável,
> considere rodar com `--alerta-js` nesse cenário.

---

## 4. Conectividade WSL → Windows

O Chrome roda no Windows e o script roda no WSL, então eles precisam se enxergar.

### Caso A — `localhost` funciona (mais comum hoje)

Se o `curl -s http://localhost:9222/json/version` acima respondeu, está tudo certo:
seu WSL está em **modo de rede espelhada (mirrored)** e o `localhost` do WSL
alcança o `localhost` do Windows. Não precisa fazer mais nada — o padrão do script
é `--host localhost`.

### Caso B — `localhost` não responde

No modo de rede padrão (NAT), o WSL2 **não** alcança o `localhost` do Windows.
A solução recomendada é habilitar o modo espelhado. Crie ou edite o arquivo
`C:\Users\<seu-usuário>\.wslconfig` no Windows:

```ini
[wsl2]
networkingMode=mirrored
```

E reinicie o WSL a partir do PowerShell:

```powershell
wsl --shutdown
```

**Alternativa (não recomendada):** apontar o script para o IP do Windows.

```bash
# descobre o IP do host Windows visto do WSL
ip route show default | awk '{print $3}'

.venv/bin/python monitor.py --host 192.168.0.1
```

Para isso funcionar, o Chrome precisaria ser aberto também com
`--remote-debugging-address=0.0.0.0` e o firewall do Windows liberado.
**Evite:** isso expõe o controle total do seu navegador (incluindo sessões
logadas) para qualquer máquina da sua rede local. Prefira o modo espelhado.

---

## 5. Como rodar

Com o Chrome preparado e a aba do SEC aberta e logada:

```bash
cd ~/jbabo/projects/anatel-monitor
.venv/bin/python monitor.py
```

Saída típica:

```
[21/08 14:48:32] Monitorando https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp
[21/08 14:48:32] Refresh a cada 30-60s (aleatorio). Ctrl+C para parar.
[21/08 14:48:37] tentativa 1: nada ainda (pagina informa que nao ha agendas disponiveis)
[21/08 14:48:37] proximo refresh em 42.3s
[21/08 14:49:22] tentativa 2: nada ainda (pagina informa que nao ha agendas disponiveis)
```

Para parar, pressione **Ctrl+C**.

### Recomendado: com alerta visual no navegador

```bash
.venv/bin/python monitor.py --alerta-js
```

### Deixando rodando por muito tempo

Se você fechar o terminal do VS Code, o script morre junto. Para deixar rodando o
dia inteiro, use o `nohup` (a saída vai para um arquivo de log):

```bash
nohup .venv/bin/python monitor.py > monitor.log 2>&1 &

# acompanhar o log em tempo real
tail -f monitor.log

# parar depois
pkill -f monitor.py
```

---

## 6. Opções de linha de comando

```
usage: monitor.py [-h] [--host HOST] [--porta PORTA] [--min MINIMO]
                  [--max MAXIMO] [--url URL] [--alerta-js] [--sem-refresh]
                  [--parar-ao-achar]
```

| Opção | Padrão | O que faz |
| --- | --- | --- |
| `--host HOST` | `localhost` | Endereço do navegador. Só mude se o `localhost` do WSL não alcançar o Windows (ver [seção 4](#4-conectividade-wsl--windows)). |
| `--porta PORTA` | `9222` | Porta de depuração remota. Precisa bater com a usada no `--remote-debugging-port`. |
| `--min MINIMO` | `30` | Tempo **mínimo**, em segundos, entre um F5 e o próximo. |
| `--max MAXIMO` | `60` | Tempo **máximo**, em segundos. O intervalo real é sorteado aleatoriamente entre `--min` e `--max` a cada ciclo, para o tráfego não ficar com cara de robô. |
| `--url URL` | a URL do SEC | Fragmento de URL usado para localizar a aba certa entre as abas abertas. |
| `--alerta-js` | desligado | Dispara um `window.alert()` de verdade na aba quando achar agenda. Como um alert aberto trava qualquer comando do Selenium, o script **encerra logo após disparar**. |
| `--sem-refresh` | desligado | Só inspeciona a página, sem dar F5. Útil para testar a detecção sem mexer na sua sessão. |
| `--parar-ao-achar` | desligado | Encerra o monitor no primeiro alerta, em vez de continuar monitorando. |

Exemplos:

```bash
# monitoramento mais espaçado, para deixar rodando o dia todo
.venv/bin/python monitor.py --min 60 --max 120

# checagem única do estado atual, sem recarregar a página
.venv/bin/python monitor.py --sem-refresh --parar-ao-achar

# outra porta de depuração
.venv/bin/python monitor.py --porta 9333
```

---

## 7. Como os alertas funcionam

Quando o script identifica agenda, ele dispara **vários avisos ao mesmo tempo**,
para maximizar a chance de você perceber:

1. **Bipe no terminal** — imprime o caractere `\a` cinco vezes.
   *(Depende de o seu terminal ter o som de alerta habilitado.)*
2. **Caixa de mensagem no Windows** — usa o `powershell.exe` para exibir um
   `MessageBox` nativo. Exige a interoperabilidade do WSL ativada
   (ver [seção 3.4](#34-usuários-de-wsl-confira-a-interoperabilidade-com-o-windows)).
3. **Fallback no Linux** — se o `powershell.exe` não existir ou não puder ser
   executado, tenta o `notify-send`.
4. **Aviso dentro da própria aba**, em um dos dois modos:
   - **Padrão:** injeta uma **faixa vermelha fixa no topo da página** e muda o
     título da aba para `>>> AGENDA DISPONIVEL <<<`. Não bloqueia nada, então o
     monitor **continua rodando**.
   - **Com `--alerta-js`:** dispara um `window.alert()` clássico. Ele é chamado
     dentro de um `setTimeout` para não travar a chamada do Selenium, mas, enquanto
     a caixa estiver aberta, o navegador não aceita mais comandos — por isso o
     script **encerra em seguida** e deixa o alerta na tela esperando o seu OK.

---

## 8. Como a detecção funciona

A cada ciclo, o script:

1. Dá um `driver.refresh()` (equivalente ao F5) na aba do SEC.
2. Espera 3 segundos para a página ASP terminar de renderizar.
3. Lê o texto visível do `<body>` e o **normaliza**: converte para minúsculas,
   remove acentos e colapsa espaços. Assim `"Não há agendas disponíveis"` vira
   `"nao ha agendas disponiveis"`, e a comparação não quebra por causa de acento
   ou de mudança de capitalização no site.
4. Aplica as regras abaixo, **nesta ordem**:

| Ordem | Verificação | Resultado |
| --- | --- | --- |
| 1 | O texto **não** contém `relacao de prova` | ❌ `tela inesperada (sessao expirada ou pagina de erro?)` — evita alarme falso quando a sessão cai |
| 2 | O texto contém alguma frase de `PADROES_SEM_AGENDA` (ex.: `nao ha agenda`) | ❌ sem agenda |
| 3 | Foram encontradas datas no formato `dd/mm/aaaa` no corpo da página | ✅ **alerta**, listando as datas |
| 4 | O texto contém alguma frase de `PADROES_COM_AGENDA` (ex.: `vagas disponiveis`) | ✅ **alerta** |
| 5 | Nenhuma das anteriores | ✅ **alerta** — a mensagem de "não há agendas" simplesmente sumiu, o que já merece uma olhada |

A verificação nº 1 é a rede de segurança: ela garante que estamos mesmo na tela
certa e logados antes de concluir qualquer coisa sobre a agenda.

As listas `PADROES_SEM_AGENDA`, `PADROES_COM_AGENDA` e a constante `MARCADOR_TELA`
ficam no topo do [monitor.py](monitor.py) e podem ser ajustadas se a Anatel mudar
os textos do sistema. **Escreva sempre sem acento e em minúsculas**, já que a
comparação é feita contra o texto normalizado.

---

## 9. Solução de problemas

### `cannot connect to chrome at localhost:9222`

O Chrome não está com a porta de depuração aberta, ou o WSL não alcança o Windows.
Refaça as seções [3](#3-preparando-o-chrome) e [4](#4-conectividade-wsl--windows).
Teste com `curl -s http://localhost:9222/json/version`.

### `This version of ChromeDriver only supports Chrome version 152 / Current browser version is 151`

Esse erro acontecia porque, ao conectar por `debuggerAddress`, o Selenium Manager
não consegue inspecionar o navegador remoto e acaba baixando sempre o driver da
versão *stable* mais recente.

**Já está resolvido no script:** a função `detectar_versao()` consulta
`http://host:porta/json/version`, extrai a versão *major* do Chrome (ex.: `151`) e
a informa ao Selenium Manager via `options.browser_version`. Assim o driver correto
é baixado automaticamente, mesmo depois de o Chrome atualizar.

Se ainda assim falhar, limpe o cache de drivers e tente de novo:

```bash
rm -rf ~/.cache/selenium
```

### `Nenhuma aba aberta com a URL contendo '...'`

A aba do SEC foi fechada, ou a URL mudou. Reabra
`https://sistemas.anatel.gov.br/SEC/Inscricao/Incluir/Tela.asp` na janela do Chrome
com depuração ligada. Confira com:

```bash
curl -s http://localhost:9222/json/list | grep -o '"url": "[^"]*anatel[^"]*"'
```

### `tela inesperada (sessao expirada ou pagina de erro?)`

Sua sessão no SEC caiu ou o site devolveu uma página de erro. Volte ao Chrome,
refaça o login (e o captcha) e reinicie o script. Como o monitor dá F5
periodicamente, na prática a sessão tende a se manter viva.

### O alerta não faz som

O `\a` depende da configuração de som do terminal. No VS Code, habilite
`terminal.integrated.enableBell` nas configurações. De qualquer forma, a caixa de
mensagem do Windows e a faixa vermelha na página continuam funcionando.

### `powershell.exe: cannot execute binary file: Exec format error`

A interoperabilidade WSL→Windows está desativada, então a caixa de mensagem do
Windows não aparece. O monitor segue funcionando normalmente com os outros
alertas. Para corrigir, veja a
[seção 3.4](#34-usuários-de-wsl-confira-a-interoperabilidade-com-o-windows).

### O script parou sozinho logo após achar agenda

Comportamento esperado se você usou `--alerta-js` ou `--parar-ao-achar`.
Veja a mensagem final: `Monitor encerrado: confira a aba do navegador.`

---

## 10. Estrutura do projeto

```
anatel-monitor/
├── .venv/              # ambiente virtual (não versionado)
├── monitor.py          # o script principal
├── requirements.txt    # dependências (Selenium)
├── teste_selenium.py   # teste mínimo de conexão com o Chrome
└── README.md           # este arquivo
```

### Principais funções do [monitor.py](monitor.py)

| Função | Responsabilidade |
| --- | --- |
| `normalizar()` | Tira acentos, baixa a caixa e colapsa espaços do texto da página |
| `detectar_versao()` | Descobre a versão do Chrome remoto para casar o ChromeDriver |
| `conectar()` | Anexa o Selenium ao Chrome já aberto via `debuggerAddress` |
| `selecionar_aba()` | Encontra e foca a aba cuja URL contém o fragmento buscado |
| `coletar_estado()` | Extrai o texto normalizado e as datas visíveis na página |
| `tem_agenda()` | Aplica as regras de decisão descritas na [seção 8](#8-como-a-detecção-funciona) |
| `alertar_no_navegador()` | Injeta a faixa vermelha ou dispara o `window.alert()` |
| `alertar()` | Bipe no terminal + `MessageBox` do Windows + `notify-send` |
| `main()` | Lê os argumentos e executa o laço de monitoramento |

O [teste_selenium.py](teste_selenium.py) é um teste rápido de conectividade —
ele apenas se conecta ao Chrome e imprime o título e a URL da aba ativa.

---

## 11. Boas práticas e limitações

- **Não abuse do intervalo.** O padrão de 30–60s já é bastante agressivo para um
  sistema público. Se for deixar rodando por horas, prefira `--min 60 --max 120`.
  Requisições rápidas demais podem sobrecarregar o serviço da Anatel e levar a
  bloqueio do seu IP.
- **O script não faz inscrição.** Ele só observa e avisa. Quem clica e conclui a
  inscrição é você — inclusive porque o hCaptcha existe justamente para impedir
  automação desse passo.
- **Não contorne o captcha.** O monitor funciona com a sessão que *você* validou
  manualmente; nenhuma etapa de verificação é burlada.
- **A janela do Chrome precisa continuar aberta.** Pode ficar minimizada ou em
  outra área de trabalho, mas se você fechar o Chrome, o monitor perde a conexão.
- **A porta 9222 dá controle total do navegador** a quem conseguir acessá-la.
  Mantenha-a restrita ao `localhost` e feche a janela de depuração quando terminar.
- **Textos do site podem mudar.** Se a Anatel alterar a frase
  "Não há agendas disponíveis no momento.", ajuste `PADROES_SEM_AGENDA` no
  [monitor.py](monitor.py). Enquanto isso, a regra nº 5 da tabela de detecção age
  como rede de proteção: qualquer mudança inesperada nessa mensagem gera alerta.

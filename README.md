# Supervisão de Energia — Smart Grid

Aplicação desktop em Python e PySide6 com monitoramento serial, limites elétricos, comandos de disjuntor e histórico SQLite.

## Instalação e execução

Requer Python 3.12. No PowerShell, a partir da pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

`data/config.json` e `data/smartgrid.db` são criados automaticamente. O JSON ausente ou inválido é recuperado; valores inválidos são substituídos por padrões, preservando as demais preferências. As gravações usam substituição atômica. O banco antigo é migrado sem apagar eventos.

## Demonstração sem placa

Em um terminal:

```powershell
.\.venv\Scripts\python.exe simulador.py --tcp 8765
```

Abra a aplicação em outro terminal. No campo Porta COM, digite `socket://127.0.0.1:8765`, escolha a velocidade e clique em Conectar. A placa simulada espera o handshake antes de transmitir. Use Corte Emergencial e Rearmar Disjuntor para observar as confirmações e os eventos.

O transporte TCP permite demonstrar o protocolo e a aplicação sem instalar portas virtuais. A troca física de baud rate deve ser verificada na bancada serial; TCP não simula a taxa elétrica da UART.

Para um par de portas seriais virtuais já configurado, execute `python simulador.py --porta COM4` e selecione a outra ponta, por exemplo COM3, na aplicação. Com uma placa física, selecione a COM correspondente e implemente nela o [protocolo](docs/protocolo.md).

## Configurações e histórico

Os limites podem ser alterados na interface. Porta, velocidade, timeout e `serial.intervalo_amostragem_ms` ficam no JSON. O intervalo aceita de 100 a 60000 ms; para alterá-lo, feche a aplicação, edite o arquivo e abra novamente. O padrão é 2000 ms.

Em Últimas N leituras, selecione a quantidade e clique em Consultar. Em Período, defina início e fim; a quantidade limita o número de resultados a até 10000. A consulta é inclusiva e mostra as últimas leituras do intervalo em ordem cronológica. Os horários dos filtros e do gráfico usam o horário local; os timestamps no SQLite são normalizados em UTC.

O botão Tempo real retorna ao monitoramento. A aquisição e a gravação continuam durante a consulta histórica. Sem conexão confirmada, não são produzidas medições artificiais na interface. Registros de simulação de versões anteriores podem permanecer no banco, identificados por `origem`.

## Arquitetura

- `models/`: entidades, cálculos, limites e repositórios. Não importa QtWidgets.
- `database/`: configuração, conexão, esquema e migração do SQLite.
- `views/` e `ui/`: apresentação e captura de eventos do operador.
- `controllers/`: conexão entre View, Model e workers por sinais.
- `workers/serial_worker.py`: conexão, handshake, leitura e comandos na SerialThread.
- `workers/database_worker.py`: inicialização, gravação, configuração JSON e consultas na DatabaseThread.
- `services/protocolo.py`: codificação e decodificação JSON por linha.
- `simulador.py`: placa externa simulada em processo independente.

A GUI desenha os widgets e recebe resultados via sinais. Os workers não manipulam widgets. O worker serial usa leitura não bloqueante e polling em seu próprio event loop. Ao fechar a janela, a serial encerra a comunicação, o banco conclui os pedidos enfileirados e os objetos são liberados com `deleteLater()`. A GUI verifica a conclusão das threads sem espera bloqueante.

Potência calculada: `P = V × I`, considerando carga resistiva ou fator de potência igual a 1. As regras de tensão e corrente geram alertas; o corte e o rearme são comandos manuais confirmados pelo operador e pela placa. Uma confirmação de hardware precede a persistência do evento. Falhas de gravação são informadas ao operador.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

A verificação integrada inicia o simulador em TCP local e percorre handshake, quatro velocidades, medições, persistência, corte/rearme, histórico e perda da conexão. Requer permissão para sockets locais. A suíte também mantém verificações de configuração e migração de dados.

O projeto foi verificado com simulador. A bancada física e o firmware da equipe devem ser validados antes da apresentação.

O [roteiro de apresentação](docs/seminario.md) organiza a exposição e a demonstração em 15 a 20 minutos.

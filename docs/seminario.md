# Roteiro do seminário — 18 minutos

| Tempo | Assunto | Demonstração |
|---|---|---|
| 0–2 min | Problema e solução | Tensão, corrente, potência, alertas e histórico |
| 2–5 min | MVC | Mostrar entidades, View e Controller, explicando a responsabilidade de cada camada |
| 5–7 min | Concorrência | GUI, SerialThread e DatabaseThread; sinais, filas e encerramento cooperativo |
| 7–10 min | Comunicação | Placa em espera, handshake em 9600, ACK e início das leituras na velocidade escolhida |
| 10–12 min | Proteção | Configurar limites, observar alertas, cortar carga e rearmar; mostrar confirmações e eventos |
| 12–14 min | Histórico | Consultar últimas N leituras e um período; retornar ao tempo real |
| 14–16 min | Tolerância a falhas | Desconectar o simulador, mostrar erro e reconectar; demonstrar recuperação do JSON |
| 16–18 min | Arguição | Explicar migração, timestamps UTC, potência e confirmação dos comandos |

## Preparação

Instalar as dependências e verificar a bancada antes da aula. Para demonstração por TCP, manter o simulador e a aplicação em terminais separados. Para a bancada serial, confirmar o par de COMs ou o protocolo do firmware da placa. A demonstração TCP não comprova a troca física de baud rate.

Para testar exclusão do JSON, fechar a aplicação antes de remover o arquivo. Guardar uma cópia das preferências da demonstração. O SQLite pode permanecer: sua migração e o histórico não dependem da existência do JSON.

## Pontos para a arguição

- SQL e comunicação serial não são executados em callbacks da GUI.
- A conexão SQLite é criada e fechada na thread que executa a operação.
- O ACK do hardware antecede o evento de atuação; alterar somente a tela não confirma corte físico.
- O histórico usa consulta assíncrona e não interrompe a gravação das medições.
- A telemetria só começa depois de HELLO, ACK, troca de velocidade, START e ACK.
- O fechamento solicita parada, aguarda a conclusão sem bloquear a GUI e libera os objetos.
- `V × I` representa potência ativa na hipótese de fator de potência igual a 1.
- Cada integrante deve apresentar e explicar as contribuições reais registradas em seu usuário.

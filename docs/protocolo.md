# Protocolo serial

Cada pacote é um objeto JSON UTF-8 terminado em `\n`, com tamanho máximo de 4096 bytes. O campo `tipo` é obrigatório. Não envie NaN ou Infinity. A placa inicializa em 9600 bps, sem emitir telemetria.

## Handshake

1. Desktop abre a porta em 9600 e envia `{"tipo":"HELLO","baud_rate":38400,"intervalo_ms":2000}`.
2. Placa confirma na velocidade inicial: `{"tipo":"ACK","comando":"HELLO"}`. Após concluir a transmissão desse ACK, muda para a velocidade solicitada.
3. Desktop recebe o ACK, muda sua porta para a nova velocidade e envia `{"tipo":"START"}`.
4. Placa confirma na velocidade negociada: `{"tipo":"ACK","comando":"START","estado":"FECHADO"}`.
5. A placa passa a transmitir `{"tipo":"TELEMETRIA","tensao":220.0,"corrente":4.2,"estado":"FECHADO"}` no intervalo combinado.

As velocidades aceitas são 9600, 19200, 38400 e 115200. O desktop calcula e grava a potência; o timestamp é atribuído no recebimento. Pacotes inválidos são descartados e registrados no log.

## Comandos e saúde do link

Desktop envia `{"tipo":"DISJUNTOR","id":1,"estado":"ABERTO"}`. A placa executa o comando e responde `{"tipo":"ACK","comando":"DISJUNTOR","id":1,"estado":"ABERTO"}`. Para rearme, use `FECHADO`. O ACK precisa repetir o identificador e o estado solicitado. Apenas um comando fica pendente por vez.

O desktop envia `{"tipo":"PING"}` a cada dois segundos e espera `{"tipo":"PONG"}`. Leituras válidas também renovam a atividade do link. A ausência de resposta encerra a conexão e desabilita os comandos. O estado físico deve ser conferido na placa quando um comando expira sem ACK.

Para desligamento normal, o desktop envia `{"tipo":"STOP"}`. A placa para a telemetria, envia `{"tipo":"ACK","comando":"STOP"}` na velocidade atual e retorna a 9600. O desktop aguarda até um segundo por esse ACK antes de fechar a porta. A placa simulada também retorna à espera em 9600 após dez segundos sem comandos do desktop.

O estado físico do disjuntor deve ser preservado ao reiniciar apenas o link. Na reconexão, o ACK de START informa esse estado para sincronizar a aplicação.

# ByteBank

Sistema bancário desenvolvido em Python como Projeto Avaliativo (AV2) da disciplina BD015 - Algoritmo e Estrutura de Dados, CESAR School.

**Squad:** Lucas Barreto Rodrigues de Barros

**Professor:** Fernando Ferreira de Carvalho

## Sobre o Projeto

Esta é a versão expandida do ByteBank Nível 2: além das operações bancárias e da transferência PIX, o sistema conta com carteira de investimentos, cartão de crédito, operações com moedas estrangeiras (dólar, euro e yuan) e simulação/contratação de empréstimos.

## Funcionalidades

### Conta e Transferências
- Login por número da conta, a partir de contas fictícias já cadastradas
- Menu interativo rodando em loop contínuo
- Consulta de saldo
- Depósito e saque, com bloqueio de valores negativos e de saldo insuficiente
- Transferência PIX entre contas, com validação da chave de destino
- Cadastro de novas contas, com bloqueio de número ou chave PIX já existentes
- Validação de entradas não numéricas, tanto para valores decimais quanto para números inteiros (o programa pede a entrada novamente em vez de travar)

### Carteira de Investimentos
- Investir parte do saldo na carteira de investimentos
- Resgatar valores da carteira de volta para o saldo

### Cartão de Crédito
- Compra no cartão de crédito, debitada da fatura (não do saldo)
- Consulta do limite total e do limite disponível (limite total menos a fatura em aberto)
- Consulta da fatura atual
- Pagamento da fatura, debitado do saldo, com bloqueio de pagamento maior que a dívida existente

### Moedas Estrangeiras
- Consulta do saldo em dólar, euro e yuan, com o equivalente em reais
- Compra de moeda estrangeira usando o saldo em reais
- Venda de moeda estrangeira, convertendo de volta para o saldo em reais
- Câmbio direto entre duas moedas quaisquer, incluindo o saldo original em reais como uma das opções

### Empréstimos
- Simulação de empréstimo, mostrando valor da parcela e total a pagar sem alterar o saldo
- Contratação de empréstimo, com juros compostos de 2% ao mês, creditando o valor solicitado no saldo e registrando a dívida total
- Consulta da dívida total de empréstimos em aberto
- Pagamento da dívida, debitado do saldo, com bloqueio de pagamento maior que a dívida existente

## Estruturas de Dados Utilizadas

As contas são representadas como uma **lista de dicionários** (`contas`). Cada conta guarda, além do saldo principal, a carteira de investimentos, o limite e a fatura do cartão de crédito, a dívida de empréstimos e o saldo em cada moeda estrangeira — tudo dentro do mesmo dicionário, sem precisar de variáveis globais.

As taxas de conversão de moeda ficam em um dicionário separado (`conversao_moedas`), mapeando cada moeda ao seu valor em reais. O saldo em reais é tratado como mais uma "moeda" nas funções de câmbio, através da chave especial `"real"`.

A taxa de juros do empréstimo fica em uma constante única (`TAXA_JUROS_EMPRESTIMO_MENSAL`), usada tanto na simulação quanto na contratação, garantindo que as duas exibam sempre o mesmo cálculo.

## Contas Fictícias Pré-Cadastradas

| Número | Titular | Chave PIX | Saldo | Investimentos | Limite Cartão |
|---|---|---|---|---|---|
| 0001 | Amanda Silva | amanda@email.com | R$ 1000,00 | R$ 5000,00 | R$ 4000,00 |
| 0002 | Caio Ferreira | caio@email.com | R$ 2500,50 | R$ 3000,00 | R$ 2500,00 |
| 0003 | Douglas Alves | douglas@email.com | R$ 320,00 | R$ 1000,00 | R$ 3000,00 |

Cada conta também começa com saldo em dólar, euro e yuan, fatura e dívida de empréstimo zeradas (consulte as opções 13, 11 e 20 do menu para ver os valores).

## Como Executar

Pré-requisito: Python 3.10 ou superior (o projeto usa `match/case`).

```
python main.py
```

Ao iniciar, informe o número de uma das contas pré-cadastradas (ex: `0001`) para acessar o menu.

## Estrutura do Menu

```
[1]  Consultar Saldo
[2]  Depositar
[3]  Sacar
[4]  Transferir (PIX)
[5]  Trocar de Conta
[6]  Consultar Carteira de Investimentos
[7]  Investir
[8]  Resgatar Investimento
[9]  Consultar Limite do Cartão de Crédito
[10] Cadastrar Nova Conta
[11] Consultar Fatura do Cartão de Crédito
[12] Pagar Fatura do Cartão de Crédito
[13] Consultar Saldo em Moedas Estrangeiras
[14] Comprar Moeda Estrangeira
[15] Câmbio entre Moedas Estrangeiras
[16] Vender Moeda Estrangeira (converter para Saldo Original)
[17] Comprar no Cartão de Crédito
[18] Simular Empréstimo
[19] Contratar Empréstimo
[20] Consultar Dívida de Empréstimo
[21] Pagar Empréstimo
[0]  Sair
```

## Correções Aplicadas Nesta Versão

- **Fatura do cartão de crédito:** antes, a fatura exibida era igual ao limite total do cartão, mesmo sem nenhuma compra. Agora o limite total e a fatura (valor gasto e ainda não pago) são controlados separadamente.
- **Compra no cartão de crédito:** a função já existia no código, mas não estava conectada a nenhuma opção do menu. Foi adicionada a opção `[17]`.
- **Conversão de moedas:** passou a aceitar o saldo original em reais (`"real"`) como origem ou destino do câmbio, permitindo vender moeda estrangeira de volta para o saldo principal.
- **Chave PIX duplicada:** o cadastro de uma nova conta agora bloqueia números de conta e chaves PIX já existentes.
- **Empréstimo sem dívida registrada:** contratar um empréstimo creditava o valor no saldo, mas não guardava a dívida em lugar nenhum — não havia como consultar ou pagar depois. Agora a dívida fica registrada em `divida_emprestimo` e pode ser consultada e paga.
- **Entrada não numérica no número de parcelas:** digitar texto no lugar de um número de parcelas travava o programa. Agora o sistema pede o valor novamente, assim como já acontecia com os valores em reais.

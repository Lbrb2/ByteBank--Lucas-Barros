# ByteBank

Sistema bancário desenvolvido em Python como Projeto Avaliativo (AV2) da disciplina BD015 - Algoritmo e Estrutura de Dados, CESAR School.

**Squad:** Lucas Barreto Rodrigues de Barros

**Professor:** Fernando Ferreira de Carvalho

## Sobre o Projeto

Esta é a versão **Nível 2 (Intermediário)** do ByteBank: expansão do MVP para suportar múltiplas contas em memória e transferências via PIX entre elas.

## Funcionalidades

### Herdadas do Nível 1
- Login por número da conta, a partir de contas fictícias já cadastradas
- Menu interativo rodando em loop contínuo
- Consulta de saldo
- Depósito, com bloqueio de valores negativos
- Saque, com bloqueio de valores negativos e de saldo insuficiente
- Validação de entradas não numéricas

### Novidades do Nível 2
- Cada conta ganha uma chave PIX, além de número, titular e saldo
- Transferência PIX entre contas, com validação da chave de destino
- Débito na conta de origem e crédito na conta de destino em uma única operação
- Bloqueio de transferência para a própria conta e para chaves PIX inexistentes
- Opção de trocar de conta sem reiniciar o programa

## Estruturas de Dados Utilizadas

| Estrutura | Onde é usada |
|---|---|
| Lista de dicionários (matriz) | Cadastro de múltiplas contas (`contas`), cada uma com número, titular, chave PIX e saldo |

A busca por conta é feita por número (login) ou por chave PIX (transferência), percorrendo a lista com um laço `for`.

## Contas Fictícias Pré-Cadastradas

| Número | Titular | Chave PIX | Saldo Inicial |
|---|---|---|---|
| 0001 | Amanda Silva | amanda@email.com | R$ 1000,00 |
| 0002 | Caio Ferreira | caio@email.com | R$ 2500,50 |
| 0003 | Douglas Alves | douglas@email.com | R$ 320,00 |

## Como Executar

Pré-requisito: Python 3.10 ou superior (o projeto usa `match/case`).

```
python main.py
```

Ao iniciar, informe o número de uma das contas pré-cadastradas (ex: `0001`) para acessar o menu.

## Estrutura do Menu

```
[1] Consultar Saldo
[2] Depositar
[3] Sacar
[4] Transferir (PIX)
[5] Trocar de Conta
[0] Sair
```

## Próximos Passos

- **Nível 3:** histórico de transações como Pilha (estorno) e Fila de pagamentos agendados.

# ByteBank

Sistema bancário desenvolvido em Python como Projeto Avaliativo (AV2) da disciplina BD015 - Algoritmo e Estrutura de Dados, CESAR School.

**Squad:** Lucas Barreto Rodrigues de Barros e Felipe Saraiva

**Professor:** Fernando Ferreira de Carvalho

## Sobre o Projeto

Esta é a versão **Nível 1 (MVP)** do ByteBank: as operações bancárias fundamentais, rodando em um menu interativo contínuo.

## Funcionalidades

- Login por número da conta, a partir de uma lista de contas fictícias já cadastradas
- Menu interativo rodando em loop contínuo
- Consulta de saldo
- Depósito, com bloqueio de valores negativos
- Saque, com bloqueio de valores negativos e de saldo insuficiente
- Validação de entradas não numéricas (o programa pede o valor novamente em vez de travar)

## Estruturas de Dados Utilizadas

As contas são representadas como uma **lista de dicionários** (`contas`), cada uma com número, titular e saldo. Cada função de operação (`depositar`, `sacar`) recebe a conta como parâmetro e altera o saldo diretamente no dicionário (`conta["saldo"] += valor`).

Como o dicionário é um objeto **mutável**, alterá-lo dentro de uma função não exige a palavra-chave `global` — a função recebe uma referência ao mesmo dicionário que existe fora dela, então a mudança já é vista por todo o programa.

## Contas Fictícias Pré-Cadastradas

| Número | Titular | Saldo Inicial |
|---|---|---|
| 0001 | Amanda Silva | R$ 1000,00 |
| 0002 | Caio Ferreira | R$ 2500,50 |
| 0003 | Douglas Alves | R$ 320,00 |

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
[0] Sair
```

## Próximos Passos

- **Nível 2:** transferência PIX entre contas, com verificação de chave de destino.
- **Nível 3:** histórico de transações como Pilha (estorno) e Fila de pagamentos agendados.

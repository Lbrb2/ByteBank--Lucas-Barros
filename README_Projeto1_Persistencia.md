# Projeto 1 — Persistência do ByteBank em arquivo de texto

**Disciplina:** BD015 – Algoritmo e Estrutura de Dados
**Aula 7 –** Persistência de Dados em Arquivos
**Professor:** Fernando Ferreira de Carvalho
**Aluno:** Lucas Barreto Rodrigues de Barros
**Instituição:** CESAR School

> **Atualização (Aula 8):** com a arquitetura Cliente → ContaCorrente → Banco,
> a gravação passou a ser responsabilidade do próprio Banco, pelos métodos
> `salvar_estado()` e `carregar_estado()`. As duas funções deste projeto
> continuam existindo com os mesmos nomes e são chamadas por esses métodos.
> O módulo `persistencia.py` (JSON) foi absorvido pelo Banco e removido.
> Detalhes em `README_Arquitetura.md`.

---

## O problema

Até a Aula 6, o ByteBank sofria de **amnésia**: todo o estado vivia em memória
RAM e desaparecia quando o programa encerrava. Depositar R$ 1.000,00, fechar o
sistema e reabrir devolvia o saldo ao valor original — nada do que o cliente
fizesse sobrevivia à sessão.

O Projeto 1 pede a cura: gravar as contas em disco ao encerrar e recuperá-las
no boot.

## O que foi pedido e onde está

| Requisito do enunciado | Onde foi implementado |
|---|---|
| Função `salvar_contas_txt(contas)` | `persistencia_txt.py`, linha 254 |
| Executada automaticamente ao encerrar o sistema | `main.py` → `encerrar()` → `Banco.salvar_estado()`, chamada no `finally` do `main()` |
| Função `carregar_contas_txt()` | `persistencia_txt.py`, linha 301 |
| Executada no boot para restaurar os saldos | `main.py` → `dar_boot()` → `Banco.carregar_estado()`, primeira leitura |
| Gravação em arquivo `.txt` | `contas.txt`, formato CSV |

## Conceitos da Aula 7 aplicados

Nada aqui usa biblioteca de serialização. A montagem e a quebra de cada linha
são manuais, exatamente como a aula apresenta:

| Conceito da aula | Uso no módulo |
|---|---|
| `with open(...)` | Gravação e leitura; fecha o arquivo mesmo se der erro no meio |
| Modo `'w'` | `salvar_contas_txt` — cria na primeira vez, sobrescreve nas seguintes |
| Modo `'r'` | `carregar_contas_txt` |
| `encoding='utf-8'` | Em todas as aberturas; sem isso "Emergência" e "Cartão" corrompem |
| `arquivo.write()` | Uma linha por conta, com `\n` ao final |
| `for linha in arquivo` | Leitura **preguiçosa**, uma linha por vez, em vez de `readlines()` |
| `.strip()` | Remove o `\n` e espaços de cada linha e de cada campo |
| `.split(',')` | Separa a linha nos 28 campos |
| `FileNotFoundError` | Primeira execução: tratada como situação normal, não como erro |

## Formato do arquivo

Uma conta por linha, 28 campos separados por vírgula:

```
# numero,titular,cpf,email,telefone,chave_pix,salt,pin_hash,bloqueada,tentativas,saldo,limite,limite_cartao,fatura_cartao,cartao_numero,cartao_validade,cartao_dia_pagamento,cartao_salt_cvv,cartao_hash_cvv,cartao_total_pago,cartao_parcelas,cartao_valor_parcela,divida_emprestimo,dolar,euro,yuan,bytepoints,cofrinhos
0001,Amanda Silva,111.111.111-11,amanda@email.com,(81) 98888-1111,amanda@email.com,4f1a0b5c...,b305b3e1...,False,0,1000.00,500.00,4000.00,0.00,5123...4535,10/31,10,9c2e...,71af...,0.00,0,0.000000,0.00,200.00,150.00,1000.00,0.00,Reserva:5000.00:0.005000;Viagem:1200.00:0.007000
```

A ordem das colunas é definida uma única vez (lista `COLUNAS`) e usada tanto na
gravação quanto na leitura. Na leitura, `zip(COLUNAS, campos)` junta cada nome
ao seu valor, então o código lê `bruto["saldo"]` em vez de `campos[10]`.

As colunas `cartao_*` guardam o `CartaoDeCredito` da conta; o CVV, como o PIN,
só vai para o arquivo como hash.

Arquivos de versões anteriores continuam sendo lidos — o número de campos
identifica o formato: 27 campos (antes do limite da conta), 19 (antes da
classe `CartaoDeCredito`) ou 17 (antes da classe `Cliente`). Na próxima gravação, eles já saem no formato novo.

A primeira linha começa com `#` e documenta as colunas. O leitor ignora linhas
que começam com `#`, o que permite comentar o arquivo sem quebrá-lo — uma
vantagem do texto puro sobre formatos binários.

### O desafio do dicionário aninhado

Os **cofrinhos** são um dicionário de dicionários (`nome → {saldo, taxa}`), e
um CSV é plano. A solução foi dar a eles separadores próprios, aproveitando que
o campo é o último da linha:

```
Reserva:5000.00:0.005000;Viagem:1200.00:0.007000
└──┬──┘ └───┬───┘ └──┬───┘
 nome    saldo    taxa mensal        cofrinhos separados por ';'
```

A leitura é um `split(';')` seguido de um `split(':')` em cada pedaço.

### Por que os textos são "limpos" antes de gravar

Um titular chamado `Silva, Jr.` geraria uma linha com 29 campos em vez de 28, e
a conta seria perdida na próxima leitura. A função `limpar_texto()` troca por
espaço qualquer caractere que sirva de separador (`,` `;` `:` `\n` `\r`) antes
de a linha ser montada. É a limitação honesta do CSV manual: quem usa vírgula
como separador precisa garantir que ela não apareça nos dados.

### Por que o `salt` e o `pin_hash` estão no arquivo

Se não estivessem, cada conta recarregada receberia um PIN novo gerado pelo
construtor e o cliente não conseguiria mais entrar. O que vai para o arquivo é
só o **hash** — o PIN em texto nunca é gravado, de modo que ler o `contas.txt`
não revela a senha de ninguém. Era justamente isso que o hashing existia para
garantir.

## Tolerância a arquivo corrompido

Uma linha fora do formato **não derruba o boot**. Ela é contada e ignorada, e
as contas íntegras são recuperadas:

```
$ python main.py
3 conta(s) lida(s) de 'contas.txt'. 1 linha(s) ignorada(s) por estarem fora do formato.
```

Linhas em branco e comentários não contam como erro. Cofrinhos malformados são
descartados individualmente, para que um cofrinho quebrado não leve a conta
inteira embora.

## Convivência com a persistência em JSON

O projeto AV2 já gravava o estado completo em JSON (hoje dentro de
`Banco.salvar_estado()`). Os dois formatos coexistem, com divisão clara de
responsabilidade:

| | `contas.txt` (Projeto 1) | `dados_bytebank.json` (AV2) |
|---|---|---|
| Contas, saldos, dívidas, cofrinhos | sim | sim |
| Extrato (pilha de transações) | não | sim |
| Consentimentos de Open Banking | não | sim |
| Legível por humanos / editável no Notepad | sim | parcialmente |
| Parsing | manual (`split`) | biblioteca |

O extrato e os consentimentos são estruturas profundas (uma lista de objetos,
cada um com seus próprios campos) e não cabem com honestidade em um CSV plano.
É exatamente por isso que formatos como o JSON existem — e a comparação acima
foi o aprendizado mais útil de implementar os dois.

**No boot, os dois arquivos são lidos.** Quando ambos existem, o sistema usa o
JSON, porque contém tudo o que o TXT contém e mais; o TXT então serve de
**conferência independente** — se os saldos discordarem, o sistema avisa em vez
de seguir calado:

```
[AVISO] Divergência entre os arquivos: conta 0002: TXT=9999.99 JSON=2500.50
[AVISO] Divergência entre os arquivos: conta 0003 existe no JSON mas não no TXT
```

Quando só o `contas.txt` existe, ele reconstrói o banco sozinho. Sem nenhum dos
dois, o sistema sobe com as contas de demonstração.

## Gravação garantida no encerramento

A chamada de `encerrar()` (que aciona `banco.salvar_estado()`) está dentro de um `finally`:

```python
try:
    Interface(banco).executar()
except (KeyboardInterrupt, EOFError):
    print("\n\n[AVISO] Execução interrompida. Salvando os dados...")
finally:
    encerrar(banco)
```

Sem o `finally`, a gravação só aconteceria na saída pelo menu, e um `Ctrl+C`
devolveria o sistema à amnésia que a persistência existe para curar. Foi um
teste com a entrada interrompida que revelou isso.

## Como testar

O módulo tem um teste de ida e volta embutido, que roda sozinho:

```bash
python persistencia_txt.py
```

```
Gravadas: 2 | Lidas: 2 | Ignoradas: 0

Conta 9001 - Teste  da Silva
  cliente .....: Cliente(Teste  da Silva, 999.999.999-99) | teste@email.com | (81) 99999-0000
  saldo .......: 1692.06 -> 1692.06
  divida ......: 609.50 -> 609.50
  bytepoints ..: 42.50 -> 42.50
  cofrinhos ...: {'Reserva': {'saldo': 300.0, 'taxa_mensal': 0.005}}
  PIN confere .: True
```

Repare no titular: foi gravado como `Teste, da Silva` e voltou como
`Teste  da Silva` — a vírgula virou espaço, como esperado.

A dívida e os pontos do teste são gerados por operações de verdade (um
empréstimo e um saque), porque os atributos da conta são privados e não
aceitam atribuição direta.

Para testar o sistema inteiro:

```bash
python main.py          # deposite um valor e saia pelo [0]
cat contas.txt          # o novo saldo está gravado
python main.py          # o saldo foi restaurado
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `persistencia_txt.py` | As duas funções do Projeto 1 |
| `banco.py` | `salvar_estado()` e `carregar_estado()` chamam as funções do Projeto 1 |
| `main.py` | `dar_boot()` e `encerrar()` acionam os métodos do Banco |
| `interface.py` | `converter_valor()` aceita `1.250,50` |
| `contas.txt` | Gerado em tempo de execução (está no `.gitignore`) |

## Correção adicional

Durante os testes apareceu uma incoerência antiga, sem relação com a
persistência: o sistema **exibia** os valores no padrão brasileiro
(`R$ 1.003,00`) mas **recusava** vírgula na digitação. Digitar `1.777,77` dava
"Valor inválido". A função `Interface.converter_valor()` resolveu:

```
'100'          -> 100.0
'99,90'        -> 99.9
'1250.50'      -> 1250.5
'1.250,50'     -> 1250.5
'1.000.000,00' -> 1000000.0
'abc'          -> recusado (ValueError)
```

A regra é a vírgula definir o padrão: se ela aparece, ela é o separador decimal
e os pontos são de milhar; se não aparece, o ponto é decimal, como `float()` já
espera. Assim `99.90` continua valendo 99,90 — um `replace(".", "")` cego teria
transformado esse valor em 9.990,00.

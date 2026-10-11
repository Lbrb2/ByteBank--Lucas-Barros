# Projeto 1 — Persistência do ByteBank em arquivo de texto

**Disciplina:** BD015 – Algoritmo e Estrutura de Dados
**Aula 7 –** Persistência de Dados em Arquivos
**Professor:** Fernando Ferreira de Carvalho
**Aluno:** Lucas Barreto Rodrigues de Barros
**Instituição:** CESAR School

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
| Função `salvar_contas_txt(contas)` | `persistencia_txt.py`, linha 176 |
| Executada automaticamente ao encerrar o sistema | `main.py` → `encerrar(banco)`, chamada no `finally` do `main()` |
| Função `carregar_contas_txt()` | `persistencia_txt.py`, linha 223 |
| Executada no boot para restaurar os saldos | `main.py` → `dar_boot()`, primeira instrução |
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
| `.split(',')` | Separa a linha nos 17 campos |
| `FileNotFoundError` | Primeira execução: tratada como situação normal, não como erro |

## Formato do arquivo

Uma conta por linha, 17 campos separados por vírgula:

```
# numero,titular,cpf,chave_pix,salt,pin_hash,bloqueada,tentativas,saldo,limite_cartao,fatura_cartao,divida_emprestimo,dolar,euro,yuan,bytepoints,cofrinhos
0001,Amanda Silva,111.111.111-11,amanda@email.com,adc043c9...,59904974...,False,0,1150.00,4000.00,0.00,0.00,200.00,150.00,1000.00,17.50,Reserva:5000.00:0.005000;Viagem:1200.00:0.007000
```

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

Um titular chamado `Silva, Jr.` geraria uma linha com 18 campos em vez de 17, e
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

O projeto AV2 já tinha `persistencia.py`, que grava o estado completo em JSON.
Os dois módulos agora coexistem, com divisão clara de responsabilidade:

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

A chamada de `encerrar()` está dentro de um `finally`:

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
  saldo .......: 1234.56 -> 1234.56
  divida ......: 500.00 -> 500.00
  bytepoints ..: 42.50 -> 42.50
  cofrinhos ...: {'Reserva': {'saldo': 300.0, 'taxa_mensal': 0.005}}
  PIN confere .: True
```

Repare no titular: foi gravado como `Teste, da Silva` e voltou como
`Teste  da Silva` — a vírgula virou espaço, como esperado.

Para testar o sistema inteiro:

```bash
python main.py          # deposite um valor e saia pelo [0]
cat contas.txt          # o novo saldo está gravado
python main.py          # o saldo foi restaurado
```

## Arquivos

| Arquivo | Papel |
|---|---|
| `persistencia_txt.py` | **Novo.** As duas funções do Projeto 1 |
| `main.py` | Alterado: `dar_boot()` e `encerrar()` chamam as funções novas |
| `interface.py` | Alterado: `converter_valor()` passou a aceitar `1.250,50` |
| `persistencia.py` | Inalterado |
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

# Desafio Final — Arquitetura Completa do ByteBank

**Disciplina:** BD015 – Algoritmo e Estrutura de Dados
**Aula 8 –** Classes, encapsulamento e persistência do estado
**Professor:** Fernando Ferreira de Carvalho
**Aluno:** Lucas Barreto Rodrigues de Barros
**Instituição:** CESAR School

---

## O que foi pedido

> Construir a malha, blindar os atributos e salvar o estado no disco.

```
┌──────────────┐  possui 1   ┌────────────────────┐  pertence a  ┌──────────────────┐
│   Cliente    │────────────▶│   ContaCorrente    │─────────────▶│      Banco       │──▶ disco
│ nome, CPF,   │             │ saldo (privado),   │    muitas    │ todas as contas, │   (TXT +
│ contatos     │             │ limite, o Cliente  │              │ salvar_estado()  │    JSON)
└──────────────┘             └─────────┬──────────┘              └──────────────────┘
                                       │ tem 1
                             ┌─────────▼──────────┐
                             │  CartaoDeCredito   │
                             │ limite, saldo,     │
                             │ número, CVV...     │
                             └────────────────────┘
```

### Slide do Desafio Final

| Requisito | Onde está |
|---|---|
| Classe `Cliente` com CPF, nome e dados de contato | `cliente.py` |
| Classe `ContaCorrente` | `conta.py` |
| Saldo **privado** | `self.__saldo`, exposto só para leitura por `@property` |
| Limite | `self.__limite` (cheque especial), somente leitura |
| A conta guarda a **instância** do Cliente dono | `self.__cliente`, recebido no construtor |
| `Banco` orquestra múltiplas contas | `banco.py` |
| `Banco.salvar_estado()` persiste toda a malha | `banco.py`, grava `dados_bytebank.json` e `contas.txt` |
| Blindar os atributos | **todas** as classes de dados: nenhum atributo pode ser alterado de fora |

### Exercícios do Classroom

| Exercício | Pedido | No ByteBank |
|---|---|---|
| **1 – Cliente** | `CPF`, `nome`, `contatos` | `cpf`, `nome` e `contatos` (e-mail e telefone) |
| | `consultar_contatos()` | `Cliente.consultar_contatos()` |
| **2 – Conta corrente** | `id_cliente` | `ContaCorrente.id_cliente` (o CPF do cliente dono) |
| | `saldo`, `limite` | `saldo` e `limite` (cheque especial), somente leitura |
| | `sacar()`, `depositar()` | já existiam; o saque agora usa o limite |
| | `consultar_saldo()`, `consultar_limite()` | novos |
| | `aumentar_limite()` | novo, com teto e estorno |
| **3 – Cartão de crédito** | `nome`, `numero`, `validade`, `CVV`, `limite`, `data_pagamento`, `saldo`, outros | `cartao_credito.py` — ver a seção 3 |
| | `consultar_limite()`, `pagar()`, `parcelar_saldo()`, `consultar_saldo()` | idem |

O exercício escreve `Consutar_Contatos()`. No código o nome segue o padrão do
Python (minúsculas, palavras separadas por `_`) e a grafia correta:
`consultar_contatos()`.

---

## 1. A classe `Cliente` (exercício 1)

Separa **quem a pessoa é** de **o que ela tem**. A conta guarda dinheiro; o
cliente guarda identidade e contato.

```python
amanda = Cliente("Amanda Silva", "111.111.111-11",
                 email="amanda@email.com", telefone="(81) 98888-1111")
conta = ContaCorrente("0001", amanda, "amanda@email.com", saldo=1000.00)
```

| Atributo | Proteção | Por quê |
|---|---|---|
| `cpf` | **somente leitura** | Identifica a pessoa e liga o cliente às instituições do Open Banking |
| `nome` | setter que **valida** | Pode mudar, mas não pode ficar vazio |
| `email` | setter que **valida** | Opcional; se informado, precisa ter `@` |
| `telefone` | setter que **valida** | Opcional; se informado, precisa de ao menos 8 dígitos |

Os contatos podem ser lidos juntos, em `cliente.contatos` (um dicionário com
e-mail e telefone), ou como texto pronto, em `cliente.consultar_contatos()`:

```
Contatos de Amanda Silva
E-mail: amanda@email.com
Telefone: (81) 98888-1111
```

O dicionário de `contatos` é criado a cada leitura. Alterá-lo não altera o
cliente: para mudar o e-mail, existe o setter, que valida.

**Blindar não é proibir: é controlar.** O CPF não muda nunca; o e-mail muda, mas
só para um valor válido. O construtor usa os próprios setters
(`self.nome = nome`), então a regra existe em um único lugar.

O CPF tem o **formato** conferido (11 dígitos), mas não os dígitos
verificadores: as contas de demonstração usam CPFs como `111.111.111-11`, que o
cálculo oficial recusaria.

---

## 2. A conta corrente (exercício 2)

### `id_cliente`

A conta guarda o **objeto** `Cliente` inteiro (composição), e não só um número
que aponte para ele. O `id_cliente` é o identificador desse cliente, o CPF:

```python
conta.cliente       # o objeto Cliente
conta.id_cliente    # '111.111.111-11'
```

É pelo CPF que o Banco encontra as contas de uma pessoa e que o Open Banking
liga o cliente às outras instituições.

### O limite é o cheque especial

Com o cartão em classe própria, o `limite` da conta corrente passou a ser o
**limite da conta**: o quanto o saldo pode ficar negativo.

```
saldo disponível = saldo + limite
```

| Saldo | Limite | Disponível | Saque de R$ 1.300 |
|---|---|---|---|
| R$ 1.000 | R$ 500 | R$ 1.500 | aceito; saldo fica em **-R$ 300** |
| -R$ 300 | R$ 500 | R$ 200 | recusado |

O limite vale para **todo débito** (saque, PIX, boleto, fatura, empréstimo,
cofrinho, compra de moeda), como num banco de verdade: a regra está num lugar
só, a property `saldo_disponivel`.

Com limite zero, o comportamento é exatamente o de antes. Foi assim que a
mudança foi verificada: o teste diferencial rodou com as contas sem limite e
deu resultado idêntico ao da versão anterior.

| Método | O que faz |
|---|---|
| `consultar_saldo()` | saldo, limite e saldo disponível; avisa quando o limite está em uso |
| `consultar_limite()` | limite total, utilizado e disponível |
| `aumentar_limite(valor)` | soma ao limite, até o máximo de R$ 5.000,00 |

O aumento fica no extrato e **pode ser estornado**, mas só se o limite extra
não estiver em uso. Com R$ 1.500 de limite e saldo em -R$ 800, desfazer um
aumento de R$ 1.000 deixaria a conta R$ 300 além do limite, então o estorno é
recusado.

O estorno de outras operações também respeita o limite: o saldo pode ficar
negativo, mas nunca abaixo de `-limite`. Por exemplo, se o recebedor de um PIX
já gastou o dinheiro e o estorno o levaria além do limite dele, o estorno é
recusado e as duas contas ficam como estavam.

Valores negativos aparecem no padrão brasileiro: **-R$ 300,00**.

---

## 3. A classe `CartaoDeCredito` (exercício 3)

| Pedido no exercício | Na classe |
|---|---|
| `nome` | nome impresso, em maiúsculas (vem do `Cliente`) |
| `numero` | 16 dígitos, com dígito verificador de Luhn, o mesmo cálculo dos cartões reais |
| `validade` | `"MM/AA"`, 5 anos após a emissão; cartão vencido recusa compras |
| `CVV` | guardado **só como hash**, como o PIN; existe `confere_cvv()`, mas nenhuma forma de lê-lo |
| `limite` | o máximo que o saldo devedor pode alcançar |
| `data_pagamento` | dia do mês em que a fatura vence (1 a 28) |
| `saldo` | o que o cliente **deve** no cartão |
| outros | plano de parcelamento e o total já pago |
| `consultar_limite()` | limite total, utilizado e disponível |
| `pagar(valor)` | paga uma compra **com** o cartão: confere valor, validade e limite |
| `parcelar_saldo(parcelas)` | divide a fatura em 2 a 12 vezes, com juros de 4% ao mês |
| `consultar_saldo()` | fatura atual, próximo vencimento e parcelamento |

### A conta **tem** um cartão, e não o entrega

Antes, o limite e a fatura eram atributos soltos da `ContaCorrente`. Agora a
conta guarda um objeto `CartaoDeCredito` (composição, como faz com o `Cliente`):

```python
self.__cartao = CartaoDeCredito(cliente.nome, limite_cartao_credito)
```

O cartão tem métodos como `receber_pagamento(valor)`, que abate a fatura. Quem
deve chamá-lo é a conta, **depois** de tirar o dinheiro do saldo. Se a conta
tivesse uma property `conta.cartao`, qualquer um poderia fazer:

```python
conta.cartao.receber_pagamento(5000)    # fatura quitada sem pagar nada
```

Por isso não existe `conta.cartao`. A conta oferece só informações
(`resumo_cartao()`, `dados_cartao()`, `fatura_cartao_credito`) e operações que
ela mesma controla:

| Na conta | O que faz |
|---|---|
| `comprar_no_cartao(valor, categoria)` | o cartão aprova (`pagar`); a conta registra no extrato e dá os pontos |
| `pagar_fatura(valor)` | confere tudo, tira o dinheiro da conta e só então o cartão abate a fatura |
| `simular_parcelamento_fatura(n)` | mostra parcelas e total antes de confirmar |
| `parcelar_fatura(n)` | parcela e registra no extrato |

### Estorno com o cartão

O estorno não pode mexer no saldo do cartão diretamente, porque é privado do
cartão. A conta pede a operação correspondente, e o cartão pode recusar:

| Transação | Estornar | Refazer |
|---|---|---|
| `COMPRA_CARTAO` | `cartao.estornar_compra(valor)` | `cartao.pagar(valor)` |
| `PAGAMENTO_FATURA` | `cartao.estornar_pagamento(valor)` | `cartao.receber_pagamento(valor)` |

Cada operação tem trava própria. `estornar_pagamento` só aceita até o total
efetivamente pago, para não ser possível "desfazer" um pagamento que nunca
existiu.

Para a atomicidade (se algo falhar, nada muda), a foto da conta tirada antes do
estorno inclui uma **cópia completa do cartão** (`copy.deepcopy`). Para
desfazer, a conta volta a usar a cópia, sem precisar de nenhum método que
altere o cartão por fora.

O **parcelamento não pode ser estornado**, como num banco de verdade: os juros
já fazem parte da dívida. Já o estorno do pagamento que **quitou** um
parcelamento devolve a dívida *e* o plano de parcelas, que o cartão guarda para
esse caso.

---

## 4. As três camadas da blindagem

Proteger de verdade exigiu fechar três portas diferentes. Fechar só a primeira
daria uma blindagem de fachada.

### Camada 1 — Atributos privados com leitura controlada

Todo atributo de toda classe de dados é privado (`__`). Para ler, existe uma
`@property` **sem setter**:

```python
>>> conta.saldo
1000.0
>>> conta.saldo = 999999
AttributeError: property 'saldo' of 'ContaCorrente' object has no setter
```

Para **coleções**, só a property não basta. Se ela devolvesse o dicionário
original, isto funcionaria:

```python
conta.cofrinhos["Reserva"]["saldo"] = 1e9   # a property entregou a referência!
```

Por isso cada coleção é entregue de um jeito que corta a ligação com o objeto:

| O que é lido | Como é entregue |
|---|---|
| `conta.cofrinhos` | cópia — inclusive de cada cofrinho, porque o dicionário é aninhado |
| `conta.historico` | tupla — não aceita `append` nem `pop` |
| `conta.consentimentos` | cópia do dicionário |
| `banco.contas` | tupla — um `append` por fora quebraria a ordem da busca binária |
| `transacao.detalhes` | cópia |
| `instituicao.dados_do_cliente(cpf)` | cópia |
| `consentimento.escopos` | tupla — não dá para incluir escopos depois da autorização |
| `conta.pin_hash`, `conta.pilha_refazer`, `banco.registro_operacoes` | **sem leitura externa** |

A `Transacao` virou **imutável**: o estorno devolve o valor gravado nela, então
alterar `transacao.valor` depois seria uma forma de fabricar saldo.

### Camada 2 — Métodos que eram portas dos fundos

Com os atributos fechados, ainda sobravam **métodos públicos** que faziam o
mesmo estrago. Eles existiam porque o Banco precisava mexer em duas contas ao
mesmo tempo (PIX e estorno de PIX):

```python
conta.creditar(1e9)                             # dinheiro sem registro
conta.reaplicar(Transacao("DEPOSITO", 1e9))     # depósito que nunca aconteceu
conta.empilhar(Transacao("SAQUE", 1e6))         # um estorno depois "devolveria" o saque
conta.ajustar_saldo_moeda("real", 1e9)
conta.restaurar({"saldo": 1e9})
conta.definir_pin("0000")                       # troca o PIN sem saber o atual
banco.registrar(conta, "...", "...")            # entrada falsa no log de auditoria
instituicao.creditar(cpf, 1e9)                  # saldo inventado na parceira,
                                                # trazido depois por portabilidade
```

**A solução foi mover as operações para dentro da conta.** Em Python (como em
Java e C++), a privacidade é da **classe**, não do objeto: dentro de um método
de `ContaCorrente`, `destino.__saldo` acessa o atributo privado de **outra**
`ContaCorrente`. Fora da classe, ninguém consegue.

```python
def enviar_pix(self, destino, valor):
    ...validações...
    self.__saldo -= valor
    destino.__saldo += valor          # outra conta, mesma classe: permitido
    pontos = self.__acumular_pontos(valor)
    self.__empilhar(Transacao("PIX_ENVIADO", ...))
    destino.__empilhar(Transacao("PIX_RECEBIDO", ...))
```

A conta agora tem quatro operações completas, e todos os auxiliares ficaram
privados:

| Operação | O que faz |
|---|---|
| `enviar_pix(destino, valor)` | débito, crédito, pontos e os dois extratos, juntos |
| `receber_portabilidade(valor, ...)` | entrada vinda de outra instituição, sempre registrada |
| `estornar_ultima(conta_par)` | desfaz o topo da pilha (e o espelho do PIX na outra conta) |
| `refazer_ultima(conta_par)` | refaz **somente** o que esta conta estornou antes |

O estorno e o refazer de PIX são **atômicos**: o método privado
`__aplicar_em_conjunto` aplica o efeito nas duas contas e, se qualquer uma
ficar com valor negativo, devolve as duas ao estado anterior.

O Banco ficou com o que é dele: localizar a outra conta, coordenar a
instituição parceira e registrar no log.

No Open Banking, o `creditar` da parceira virou **`devolver`**, que só aceita
devolver o que de fato saiu dela por portabilidade:

```python
>>> instituicao.devolver(cpf, 1e9)
(False, 'Banco Nacional só pode receber de volta valores que saíram dela por portabilidade.')
```

### Camada 3 — `__slots__`: nada de atributos novos

Mesmo com tudo isso, um teste revelou um comportamento enganoso:

```python
banco.fila_boletos = []      # não dava erro nenhum!
```

Como não existe property com esse nome, o Python simplesmente **criava um
atributo novo e solto** no objeto. A fila verdadeira (`_Banco__fila_boletos`)
continuava intacta, mas o comando passava em silêncio e quem testasse acharia
que tinha apagado a fila.

`__slots__` fixa a lista de atributos que o objeto pode ter. Agora:

```python
>>> banco.fila_boletos = []
AttributeError: 'Banco' object has no attribute 'fila_boletos' and no __dict__ for setting new attributes
```

Todas as classes têm `__slots__`: `Cliente`, `ContaCorrente`, `CartaoDeCredito`, `Transacao`,
`Banco`, `InstituicaoParceira`, `Consentimento`, `Diretorio` e `Interface`.

### Sobre o `__` em Python

Dentro da classe, `self.__saldo` vira `self._ContaCorrente__saldo` (*name
mangling*). Não é uma tranca absoluta — Python não tem uma; quem escrever
`conta._ContaCorrente__saldo` de propósito consegue acessar. O que o mecanismo
garante é que ninguém acesse **por engano** e que fique explícito o que não faz
parte da interface pública da classe.

Um efeito colateral: código que alterava campos pelo nome em texto, como
`setattr(self, "saldo_dolar", valor)` no câmbio e no estorno, parou de
funcionar, porque `saldo_dolar` agora é uma property sem setter. O método
privado `__definir_campo_financeiro` escreve no nome verdadeiro
(`_ContaCorrente__saldo_dolar`) e só aceita os campos da lista
`CAMPOS_FINANCEIROS`, para nunca poder ser usado para mexer no PIN ou no bloqueio.

### O que a blindagem não cobre (e por quê)

- **Criar objetos novos.** `ContaCorrente(..., saldo=1e9)` cria uma conta com
  esse saldo. Encapsulamento protege um objeto depois de criado; quem pode
  criar contas é uma questão de autorização. O Banco, porém, só aceita a conta
  por `adicionar_conta`, que recusa número, CPF ou chave PIX repetidos.
- **`depositar`** continua público: é uma entrada de dinheiro legítima e sempre
  fica no extrato.
- **`para_dicionario()`** inclui o hash do PIN, porque é ele que vai para o
  disco. Não existe outra forma de lê-lo.
- **Revogar um consentimento** pelo objeto recebido
  (`conta.consentimentos["BNC01"].revogar()`) funciona. Revogar só reduz
  acesso, nunca amplia, e um consentimento revogado não pode ser reativado.

---

## 5. `Banco.salvar_estado()` e `Banco.carregar_estado()`

O Banco é o contêiner que conhece todas as contas, então é ele quem sabe se
gravar por inteiro. O antigo `persistencia.py` foi absorvido pela classe e
**removido**.

| Arquivo | Conteúdo |
|---|---|
| `dados_bytebank.json` | Estado completo: contas com extrato e consentimentos, fila de boletos, log de auditoria, Open Banking |
| `contas.txt` | Contas e saldos, pelas funções do Projeto 1 (`salvar_contas_txt` / `carregar_contas_txt`) |

O JSON é montado **inteiro antes de o arquivo ser aberto**. O modo `'w'` apaga
o conteúdo no momento em que abre; se o texto fosse montado depois e algo desse
errado no meio, o arquivo antigo já estaria perdido.

O `persistencia_txt.py` não toca em nenhum atributo privado: grava a partir de
`conta.para_dicionario()` e lê entregando um dicionário para
`ContaCorrente.de_dicionario()`, que reconstrói e valida a conta.

### Compatibilidade com arquivos antigos

| Arquivo | Como é tratado |
|---|---|
| JSON de antes da classe `Cliente` (titular e CPF soltos) | `de_dicionario` cria o `Cliente` a partir deles |
| `contas.txt` de 17 colunas (sem e-mail e telefone) | o número de colunas identifica o formato |
| arquivos de antes do limite da conta | a conta abre com limite zero; ele pode ser aumentado pelo menu |
| arquivos de antes da classe `CartaoDeCredito` (só limite e fatura) | o cartão é criado com o limite e a fatura gravados; o total já pago é reconstruído a partir dos `PAGAMENTO_FATURA` do extrato, para que pagamentos antigos possam ser estornados |
| JSON sem o registro do que cada parceira portou | reconstruído a partir dos extratos: toda `PORTABILIDADE` ainda no histórico é dinheiro que saiu da parceira e não voltou |

Sem a última linha, uma portabilidade feita antes desta atualização não
poderia mais ser estornada — foi um teste com um arquivo da versão anterior
que mostrou isso.

---

## 6. Como foi testado

**53 de 53 tentativas de alteração indevida barradas**, entre elas:

```
conta.saldo = 0                        AttributeError
conta.cofrinhos = {}                   AttributeError
conta.historico.append(...)            AttributeError   (tupla)
conta.creditar(1e9)                    AttributeError   (não existe mais)
conta.reaplicar(Transacao(...))        AttributeError   (privado)
conta.definir_pin("0000")              AttributeError   (privado)
transacao.valor = 1e9                  AttributeError
banco.contas.append(conta)             AttributeError   (tupla)
banco.registrar(conta, "fraude")       AttributeError   (privado)
banco.fila_boletos = []                AttributeError   (__slots__)
consentimento.ativo = True             AttributeError
instituicao.creditar(cpf, 1e9)         AttributeError   (virou devolver)
cliente.cpf = "000.000.000-00"         AttributeError
cliente.email = "semarroba"            ValueError
```

Também foi conferido que alterar as **cópias** recebidas (cofrinhos, detalhes
da transação, dados da parceira) não altera o objeto original, e que o saldo e
o log continuam idênticos depois de todas as tentativas.

**Nenhuma regressão — teste diferencial.** A mesma sequência de **74
operações** foi executada na versão anterior e na nova: depósito, saque, PIX
(inclusive para si mesmo, sem saldo e com valor negativo), estorno e refazer de
PIX pelos dois lados, **estorno de PIX recusado porque o recebedor já tinha
gastado o dinheiro** (as duas contas ficam intactas), câmbio, cofrinhos,
cartão, empréstimo, boletos, pontos, portabilidade com estorno e refazer,
consentimentos, bloqueio por PIN e cadastro. As 935 linhas de resultado —
mensagens, saldos de todas as contas, extratos e log — são **idênticas**; só
mudam os horários.

**Persistência:** arquivos das duas versões anteriores abrem corretamente;
portabilidade feita na versão anterior pode ser estornada; portar → fechar →
abrir → estornar → refazer funciona; linha duplicada no `contas.txt` é
ignorada com aviso; `Ctrl+D` no meio de uma operação ainda grava os arquivos.

**Cartão de crédito:** compra, pagamento parcial e total, estorno e refazer
de cada um; estorno de compra recusado quando a fatura já foi paga; parcelamento
recusado acima de 12 vezes, quando os juros estouram o limite ou quando já há
um parcelamento; estorno do parcelamento recusado; estorno da quitação
devolvendo o plano de parcelas; recusa do cartão desfazendo tudo (rollback);
cartão gravado e restaurado pelo JSON e pelo TXT (número, validade, hash do
CVV e parcelamento); arquivos da versão anterior com fatura e pagamento,
inclusive o estorno do pagamento antigo. Na regressão diferencial, a única
mudança é o texto de "Consultar Limite e Fatura", que agora mostra o cartão.

**Exercícios 1 e 2:** `consultar_contatos()`; saque, PIX, boleto e compra de
moeda usando o limite; recusa além do limite; aumento de limite dentro e fora
do teto; estorno do aumento aceito quando só o limite base está em uso e
recusado quando o limite extra está em uso; estorno de PIX recusado quando
levaria o recebedor além do limite; saldo negativo gravado e restaurado pelo
JSON e pelo TXT; linha de TXT editada com saldo abaixo do limite é ignorada.
Com as contas sem limite, a regressão diferencial é idêntica à da versão
anterior.

**Pelo menu:** PIX de uma conta, reinício do sistema, estorno do PIX pela conta
que **recebeu** — as duas contas voltam juntas aos valores originais.

---

## Arquivos

| Arquivo | Situação |
|---|---|
| `cliente.py` | **Novo** — classe `Cliente`, com `consultar_contatos()` |
| `cartao_credito.py` | **Novo** — classe `CartaoDeCredito` |
| `conta.py` | `ContaCorrente`: todos os atributos privados, operações entre contas, auxiliares privados; o cartão passou para a classe própria; limite da conta, `id_cliente`, `consultar_saldo()`, `consultar_limite()` e `aumentar_limite()` |
| `banco.py` | atributos e log privados; `salvar_estado()`, `carregar_estado()`; PIX, estorno e refazer delegados à conta |
| `transacao.py` | `Transacao` imutável |
| `open_banking.py` | atributos privados; `creditar` virou `devolver`, com registro do que foi portado |
| `interface.py` | `__slots__`; cadastro pede e-mail e telefone; submenu do cartão com parcelamento e dados do cartão; consultar e aumentar o limite da conta; meus dados de contato |
| `persistencia_txt.py` | conversa com a conta só por dicionários; colunas de e-mail, telefone, limite da conta e do cartão |
| `main.py` | contas de demonstração com `Cliente`; boot e encerramento pelo Banco |
| `persistencia.py` | **Removido** — absorvido por `Banco.salvar_estado()` |
| `formatacao.py` | valores negativos no padrão brasileiro (-R$ 300,00) |
| `seguranca.py` | Inalterado |

## Como testar

```bash
python main.py                  # conta 0001, PIN 1111
python persistencia_txt.py      # teste de ida e volta do arquivo de texto
```

```python
from cliente import Cliente
from conta import ContaCorrente

conta = ContaCorrente("0100", Cliente("Ana", "123.456.789-00"), "ana@pix", saldo=100)
conta.saldo                  # 100 — leitura liberada
conta.saldo = 0              # AttributeError — escrita bloqueada
conta.cofrinhos["x"] = {}    # altera só a cópia recebida
conta.qualquer_coisa = 1     # AttributeError — __slots__
```

(A mensagem exata dos erros varia com a versão do Python.)

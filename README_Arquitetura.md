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
│ e-mail, tel. │             │ limite, o Cliente  │              │ salvar_estado()  │    JSON)
└──────────────┘             └────────────────────┘              └──────────────────┘
```

| Requisito do slide | Onde está |
|---|---|
| Classe `Cliente` com CPF, nome e dados de contato | `cliente.py` |
| Classe `ContaCorrente` | `conta.py` |
| Saldo **privado** | `self.__saldo`, exposto só para leitura por `@property` |
| Limite | `self.__limite_cartao_credito`, somente leitura |
| A conta guarda a **instância** do Cliente dono | `self.__cliente`, recebido no construtor |
| `Banco` orquestra múltiplas contas | `banco.py` |
| `Banco.salvar_estado()` persiste toda a malha | `banco.py`, grava `dados_bytebank.json` e `contas.txt` |
| Blindar os atributos | **todas** as classes de dados: nenhum atributo pode ser alterado de fora |

---

## 1. A classe `Cliente`

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

**Blindar não é proibir: é controlar.** O CPF não muda nunca; o e-mail muda, mas
só para um valor válido. O construtor usa os próprios setters
(`self.nome = nome`), então a regra existe em um único lugar.

O CPF tem o **formato** conferido (11 dígitos), mas não os dígitos
verificadores: as contas de demonstração usam CPFs como `111.111.111-11`, que o
cálculo oficial recusaria.

---

## 2. As três camadas da blindagem

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

Todas as classes têm `__slots__`: `Cliente`, `ContaCorrente`, `Transacao`,
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

## 3. `Banco.salvar_estado()` e `Banco.carregar_estado()`

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
| JSON sem o registro do que cada parceira portou | reconstruído a partir dos extratos: toda `PORTABILIDADE` ainda no histórico é dinheiro que saiu da parceira e não voltou |

Sem a última linha, uma portabilidade feita antes desta atualização não
poderia mais ser estornada — foi um teste com um arquivo da versão anterior
que mostrou isso.

---

## 4. Como foi testado

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

**Pelo menu:** PIX de uma conta, reinício do sistema, estorno do PIX pela conta
que **recebeu** — as duas contas voltam juntas aos valores originais.

---

## Arquivos

| Arquivo | Situação |
|---|---|
| `cliente.py` | **Novo** — classe `Cliente` |
| `conta.py` | `ContaCorrente`: todos os atributos privados, operações entre contas, auxiliares privados |
| `banco.py` | atributos e log privados; `salvar_estado()`, `carregar_estado()`; PIX, estorno e refazer delegados à conta |
| `transacao.py` | `Transacao` imutável |
| `open_banking.py` | atributos privados; `creditar` virou `devolver`, com registro do que foi portado |
| `interface.py` | `__slots__`; cadastro pede e-mail e telefone |
| `persistencia_txt.py` | conversa com a conta só por dicionários; colunas de e-mail e telefone |
| `main.py` | contas de demonstração com `Cliente`; boot e encerramento pelo Banco |
| `persistencia.py` | **Removido** — absorvido por `Banco.salvar_estado()` |
| `formatacao.py`, `seguranca.py` | Inalterados |

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

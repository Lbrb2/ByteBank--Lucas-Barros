# ByteBank

Sistema bancário desenvolvido em Python como Projeto Avaliativo (AV2) da disciplina BD015 - Algoritmo e Estrutura de Dados, CESAR School.

**Squad:** Lucas Barreto Rodrigues de Barros

**Professor:** Fernando Ferreira de Carvalho

## Sobre o Projeto

O ByteBank simula as operações centrais de uma FinTech moderna, do atendimento ao cliente ao processamento de estruturas lineares avançadas (Listas, Pilhas e Filas). O projeto cobre os três níveis obrigatórios da especificação, implementa **todas as seis funcionalidades do cardápio de bônus** e acrescenta cinco módulos autorais, organizado em classes e módulos separados.

## Como Executar

Pré-requisito: Python 3.10 ou superior (o projeto usa `match/case`). Não há dependências externas.

```
python main.py
```

### Contas de demonstração

| Conta | Titular | CPF | PIN | Saldo | Cofrinhos |
|---|---|---|---|---|---|
| 0001 | Amanda Silva | 111.111.111-11 | **1111** | R$ 1.000,00 | Reserva, Viagem |
| 0002 | Caio Ferreira | 222.222.222-22 | **2222** | R$ 2.500,50 | Reserva |
| 0003 | Douglas Alves | 333.333.333-33 | **3333** | R$ 320,00 | Emergência |

O login aceita **número da conta ou CPF**, seguido do PIN.

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Ponto de entrada: carrega os dados e inicia a interface |
| `conta.py` | Classe `Conta` — dados e operações de uma conta individual |
| `banco.py` | Classe `Banco` — coleção de contas, PIX, estornos, fila, log e Open Banking |
| `interface.py` | Classe `Interface` — menus, leitura de entrada e exibição |
| `transacao.py` | Classe `Transacao` — item da pilha de histórico |
| `open_banking.py` | Instituições parceiras, consentimentos e diretório |
| `seguranca.py` | Hash de PIN com salt |
| `persistencia.py` | Gravação e leitura do estado em JSON |
| `formatacao.py` | Formatação financeira brasileira e layout dos painéis |

**Separação entre lógica e apresentação:** os métodos de `Conta` e `Banco` não imprimem nada — devolvem `(sucesso, mensagem)`. Quem exibe é a `Interface`. Isso mantém as regras de negócio testáveis de forma independente da tela.

**Divisão entre `Conta` e `Banco`:** operações de uma conta só (depósito, saque, cofrinhos, cartão, câmbio, empréstimo) ficam em `Conta`. Operações entre contas ou do sistema inteiro (PIX, estorno, fila de boletos, log, Open Banking) ficam em `Banco`.

## Níveis Obrigatórios

### Nível 1 — Operações Básicas e Interface
- Menu interativo em loop contínuo (`while True`) com encerramento amigável
- Depósito com validação de valores negativos e nulos
- Saque com validação de saldo insuficiente, valores negativos e **limite por operação** (R$ 2.000,00)
- Tratamento de exceções (`try/except`) impedindo crashes por entrada de texto inválida, em valores decimais, inteiros e percentuais
- Formatação financeira no padrão brasileiro via f-strings (ex: `R$ 1.250,50`)

### Nível 2 — Múltiplas Contas e Transferências PIX
- Múltiplas contas em memória, gerenciadas pela classe `Banco`
- Cadastro de novos clientes com nome, CPF, chave PIX e PIN
- Busca de conta por **número ou CPF**, além de busca por chave PIX
- Transferência PIX atômica: debita da origem e credita no destino após validar a existência da conta recebedora e o saldo disponível

### Nível 3 — Estruturas de Dados Avançadas
- **TAD Pilha (Extrato e Estorno):** cada transação é empilhada com `append()`. O estorno usa `pop()` para reverter o último movimento (LIFO). A reversão é específica por tipo — devolve ao cofrinho, reduz a fatura, reverte o câmbio nas duas moedas, retira os BytePoints ganhos, desfaz o PIX nas duas contas e devolve a portabilidade à instituição de origem. Estornos que deixariam algum valor negativo são recusados via *snapshot* e rollback.
- **TAD Fila (Pagamento de Boletos):** boletos agendados entram com `append()` e são processados na ordem de chegada com `pop(0)` (FIFO). Boletos sem saldo permanecem pendentes na fila em vez de serem descartados.

## Funcionalidades Extras (Cardápio de Bônus)

### 1. Cofrinhos / Caixinhas de Investimento
Subcontas nomeadas (dicionário `cofrinhos`), cada uma com saldo e **taxa de rendimento própria**. Permite criar, guardar, resgatar, excluir, simular e aplicar rendimento por **juros simples** (`J = C × i × t`). Simular apenas calcula; aplicar credita e gera transação estornável.

### 2. Categorização de Gastos & Analytics
Boletos e compras no cartão são classificados em 7 categorias. O relatório faz um **GROUP BY em memória** sobre a pilha, acumulando por categoria e exibindo valor, percentual e gráfico de barras, ordenado da maior despesa para a menor. Como lê a própria pilha, estornar um gasto o remove do relatório automaticamente.

### 3. Cartão de Crédito e Fatura
Limite aprovado, compras no crédito e pagamento de fatura com o saldo corrente. Limite total, limite disponível e fatura em aberto são controlados separadamente.

### 4. Carteira Multimoedas (Câmbio)
Saldos em dólar, euro e yuan com tabela de taxas. Permite comprar, vender e fazer câmbio direto entre duas moedas quaisquer — incluindo o real como uma das pontas.

### 5. Programa de Fidelidade (BytePoints)
Acúmulo de **1 ponto por R$ 1,00 gasto** em saques, PIX enviados, boletos e compras no cartão. **100 pontos valem R$ 1,00** de cashback (resgate mínimo de 100). Estornar uma operação devolve os pontos que ela gerou, impedindo acúmulo indevido.

### 6. Módulo de Empréstimos Pré-Aprovados
Crédito de até **3× o patrimônio líquido** (saldo + cofrinhos − dívida), em até 24 parcelas, com juros compostos de 2% ao mês. O uso do patrimônio *líquido* evita que o dinheiro recebido de um empréstimo aumente o próprio limite, o que permitiria contratações em cascata.

## Módulos Autorais

### 7. Open Banking
Compartilhamento de dados entre instituições, seguindo a lógica do Open Finance brasileiro:

- **Instituições parceiras** ligadas ao cliente pelo CPF
- **Consentimento explícito** com escopo granular (saldos, transações, investimentos), validade de 12 meses e revogação a qualquer momento — sem consentimento válido, nada é compartilhado
- **Visão consolidada:** agrega o patrimônio do cliente no ByteBank e em todas as instituições autorizadas
- **Portabilidade de saldo** entre instituições, preservando o patrimônio total
- **Trilha de acessos:** registro de cada consulta a dados externos, com data, instituição e escopo

### 8. Persistência em JSON
O estado completo (contas, cofrinhos, pilhas, fila, log, consentimentos) é gravado ao sair e recuperado na abertura. Arquivo corrompido ou de versão anterior não interrompe a execução: o sistema avisa e inicia com os dados de demonstração.

### 9. Busca Binária
A lista de contas é mantida ordenada por número, e a busca usa divisão pela metade — **O(log n)** em vez de O(n). Com 10.000 contas, o pior caso cai de 10.000 para 14 comparações. A inserção usa busca binária para achar a posição correta. O método `busca_sequencial` permanece no código para comparação de desempenho.

### 10. Pilha de Refazer (Redo)
Uma segunda pilha guarda o que foi estornado, permitindo reaplicar a operação. Qualquer operação nova limpa o refazer pendente — mesmo comportamento do Ctrl+Z / Ctrl+Y. Estorno e refazer compartilham um único método (`_aplicar_efeito`), que inverte o sinal do efeito em vez de duplicar a lista de tipos.

### 11. PIN com Bloqueio
Acesso protegido por PIN de 4 dígitos, com bloqueio após 3 tentativas erradas e desbloqueio mediante validação de CPF. O PIN nunca é guardado em texto: o que fica salvo é o hash (`pbkdf2_hmac`, SHA-256, 100.000 iterações) com **salt próprio por conta**, e a verificação usa `compare_digest` para não vazar informação pelo tempo de resposta.

## Estruturas de Dados Utilizadas

| Estrutura | Onde é usada | Operação |
|---|---|---|
| Lista ordenada | `Banco.contas` | Busca binária O(log n) por número |
| Pilha (LIFO) | `Conta.historico` | `append()` para registrar, `pop()` para estornar |
| Pilha (LIFO) | `Conta.pilha_refazer` | Guarda o que foi estornado, para refazer |
| Fila (FIFO) | `Banco.fila_boletos` | `append()` para agendar, `pop(0)` para processar |
| Dicionário | `Conta.cofrinhos` | Subcontas nomeadas com saldo e taxa |
| Dicionário | `Conta.consentimentos` | Autorizações do Open Banking por instituição |
| Dicionário acumulador | `gastos_por_categoria()` | GROUP BY em memória dos gastos |
| Lista de dicionários | `Banco.registro_operacoes` | Log de auditoria, filtrado por conta |

**Pilha x Log:** a pilha (`historico`) guarda as transações estornáveis e encolhe a cada estorno. O log (`registro_operacoes`) é auditoria e nunca perde informação — os próprios estornos são registrados nele. Operações recusadas não entram no log.

## Estrutura do Menu

```
[1] Conta e Saldo
    [1] Consultar Saldo              [5] Estornar Última Transação
    [2] Depositar                    [6] Refazer Transação Estornada
    [3] Sacar                        [7] Histórico de Operações
    [4] Ver Extrato (Pilha)          [8] Relatório de Gastos por Categoria

[2] Transferências e Pagamentos
    [1] Transferir (PIX)             [4] Ver Fila de Boletos
    [2] Pagar Boleto Agora           [5] Processar Boletos Agendados
    [3] Agendar Boleto (Fila)

[3] Cofrinhos (Caixinhas)
    [1] Ver Cofrinhos                [5] Simular Rendimento
    [2] Criar Cofrinho               [6] Aplicar Rendimento
    [3] Guardar Dinheiro             [7] Excluir Cofrinho
    [4] Resgatar Dinheiro

[4] Cartão de Crédito
    [1] Consultar Limite e Fatura    [3] Pagar Fatura
    [2] Comprar no Cartão de Crédito

[5] Moedas Estrangeiras
    [1] Consultar Saldo              [3] Vender Moeda Estrangeira
    [2] Comprar Moeda Estrangeira    [4] Câmbio entre Moedas

[6] Empréstimos
    [1] Consultar Crédito Pré-Aprovado   [4] Consultar Dívida
    [2] Simular Empréstimo               [5] Pagar Empréstimo
    [3] Contratar Empréstimo

[7] Programa de Fidelidade
    [1] Consultar Pontos             [2] Resgatar Pontos (cashback)

[8] Open Banking
    [1] Instituições Participantes   [5] Visão Consolidada do Patrimônio
    [2] Autorizar Compartilhamento   [6] Portabilidade de Saldo
    [3] Meus Consentimentos          [7] Trilha de Acessos
    [4] Revogar Consentimento

[9] Cadastro e Acesso
    [1] Cadastrar Nova Conta         [3] Trocar de Conta
    [2] Alterar meu PIN

[0] Sair
```

## Parâmetros do Sistema

As regras de negócio ficam em constantes no topo de `conta.py`, fáceis de ajustar:

| Constante | Valor | Significado |
|---|---|---|
| `LIMITE_MAXIMO_SAQUE_POR_OPERACAO` | R$ 2.000,00 | Teto por saque |
| `TAXA_JUROS_EMPRESTIMO_MENSAL` | 2% a.m. | Juros compostos do empréstimo |
| `MULTIPLICADOR_CREDITO_PRE_APROVADO` | 3× | Crédito sobre o patrimônio líquido |
| `MAXIMO_PARCELAS_EMPRESTIMO` | 24 | Parcelamento máximo |
| `TAXA_RENDIMENTO_MENSAL_PADRAO` | 0,5% a.m. | Rendimento padrão dos cofrinhos |
| `PONTOS_POR_REAL_GASTO` | 1 | BytePoints por real gasto |
| `PONTOS_PARA_UM_REAL` | 100 | Pontos equivalentes a R$ 1,00 |
| `MAXIMO_TENTATIVAS_PIN` | 3 | Tentativas antes do bloqueio |
| `VALIDADE_PADRAO_DIAS` | 365 | Validade do consentimento (em `open_banking.py`) |

## Observações

- O arquivo `dados_bytebank.json` é gerado em tempo de execução e não faz parte do código-fonte.
- A pilha de refazer não é persistida: o redo vale apenas para a sessão atual, como em editores de texto.

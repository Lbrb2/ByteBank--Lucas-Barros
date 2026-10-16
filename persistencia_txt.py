"""Persistência das contas em arquivo de texto puro (Projeto 1 - Aula 7).

Este módulo cumpre o Projeto 1 da Aula 7: gravar e recuperar as contas em um
arquivo .txt usando apenas as técnicas da aula — 'with open', 'write',
'for linha in arquivo', '.strip()' e '.split()'. Nenhuma biblioteca de
serialização é usada aqui: a montagem e a quebra de cada linha são manuais.

Formato de 'contas.txt' — uma conta por linha, campos separados por vírgula:

    numero,titular,cpf,email,telefone,chave_pix,salt,pin_hash,bloqueada,
    tentativas,saldo,limite,limite_cartao,fatura_cartao,
    cartao_numero,cartao_validade,cartao_dia_pagamento,cartao_salt_cvv,
    cartao_hash_cvv,cartao_total_pago,cartao_parcelas,cartao_valor_parcela,
    divida_emprestimo,dolar,euro,yuan,bytepoints,cofrinhos

As colunas 'cartao_*' guardam o CartaoDeCredito da conta. O CVV, como o PIN,
só é gravado em forma de hash.

O último campo guarda os cofrinhos, que são um dicionário aninhado. Como um
arquivo CSV é plano, eles recebem separadores próprios:

    Reserva:5000.00:0.005;Viagem:1200.00:0.007
    └──┬──┘ └───┬───┘ └─┬─┘
     nome    saldo    taxa mensal      (cofrinhos separados por ';')

Por isso os textos gravados passam por 'limpar_texto': uma vírgula no nome do
titular, ou um ';' no nome de um cofrinho, quebraria a leitura da linha.

Encapsulamento: os atributos sensíveis da ContaCorrente (saldo, PIN, bloqueio)
são privados. Este módulo não tenta acessá-los: na gravação ele usa o
dicionário que a própria conta exporta (para_dicionario) e na leitura entrega
um dicionário para a própria classe se reconstruir (de_dicionario). O arquivo
TXT só cuida do formato; quem decide o que é uma conta válida é a classe.

Relação com o JSON: este módulo guarda o estado financeiro das contas, que é
o que o Projeto 1 pede. O extrato (pilha de transações) e os consentimentos
de Open Banking são estruturas aninhadas e profundas, que só o JSON armazena.
Os dois arquivos são gravados por Banco.salvar_estado() ao encerrar o sistema
e lidos por Banco.carregar_estado() no boot.
"""

from conta import ContaCorrente
from cliente import Cliente

ARQUIVO_CONTAS = "contas.txt"

SEPARADOR_DE_CAMPO = ","
SEPARADOR_DE_COFRINHO = ";"
SEPARADOR_INTERNO = ":"
MARCA_DE_COMENTARIO = "#"

# Ordem das colunas no arquivo. Ela é definida uma única vez e usada tanto na
# gravação quanto na leitura, para que as duas nunca fiquem desencontradas.
COLUNAS = [
    "numero", "titular", "cpf", "email", "telefone", "chave_pix",
    "salt", "pin_hash", "bloqueada", "tentativas",
    "saldo", "limite", "limite_cartao", "fatura_cartao",
    "cartao_numero", "cartao_validade", "cartao_dia_pagamento", "cartao_salt_cvv",
    "cartao_hash_cvv", "cartao_total_pago", "cartao_parcelas", "cartao_valor_parcela",
    "divida_emprestimo", "dolar", "euro", "yuan", "bytepoints", "cofrinhos",
]

# Formatos gravados por versões anteriores. Continuam sendo lidos para que um
# contas.txt antigo não seja perdido; na próxima gravação, ele sai no novo.

# Antes do limite da conta corrente (sem a coluna limite)
COLUNAS_SEM_LIMITE = [coluna for coluna in COLUNAS if coluna != "limite"]

# Antes da classe CartaoDeCredito (sem as colunas cartao_*)
COLUNAS_SEM_CARTAO = [
    "numero", "titular", "cpf", "email", "telefone", "chave_pix",
    "salt", "pin_hash", "bloqueada", "tentativas",
    "saldo", "limite_cartao", "fatura_cartao", "divida_emprestimo",
    "dolar", "euro", "yuan", "bytepoints", "cofrinhos",
]

# Antes da classe Cliente (sem e-mail e telefone)
COLUNAS_VERSAO_ANTERIOR = [
    "numero", "titular", "cpf", "chave_pix",
    "salt", "pin_hash", "bloqueada", "tentativas",
    "saldo", "limite_cartao", "fatura_cartao", "divida_emprestimo",
    "dolar", "euro", "yuan", "bytepoints", "cofrinhos",
]

# O número de campos da linha identifica o formato. Linha com outra
# quantidade está corrompida e é ignorada.
FORMATOS_POR_QUANTIDADE = {
    len(COLUNAS): COLUNAS,
    len(COLUNAS_SEM_LIMITE): COLUNAS_SEM_LIMITE,
    len(COLUNAS_SEM_CARTAO): COLUNAS_SEM_CARTAO,
    len(COLUNAS_VERSAO_ANTERIOR): COLUNAS_VERSAO_ANTERIOR,
}

CABECALHO = MARCA_DE_COMENTARIO + " " + SEPARADOR_DE_CAMPO.join(COLUNAS)

CARACTERES_PROIBIDOS = (SEPARADOR_DE_CAMPO, SEPARADOR_DE_COFRINHO,
                        SEPARADOR_INTERNO, "\n", "\r")


def limpar_texto(texto):
    """Troca por espaço qualquer caractere que serviria de separador.

    Sem isso, um titular chamado 'Silva, Jr.' geraria uma linha com um campo
    extra e a conta seria perdida na próxima leitura.
    """
    resultado = str(texto)
    for proibido in CARACTERES_PROIBIDOS:
        resultado = resultado.replace(proibido, " ")
    return resultado.strip()


def montar_cofrinhos(cofrinhos):
    """Transforma o dicionário de cofrinhos em um único texto."""
    partes = []
    for nome, dados in cofrinhos.items():
        partes.append(SEPARADOR_INTERNO.join([
            limpar_texto(nome),
            f"{dados['saldo']:.2f}",
            f"{dados['taxa_mensal']:.6f}",
        ]))
    return SEPARADOR_DE_COFRINHO.join(partes)


def ler_cofrinhos(texto):
    """Desfaz o trabalho de 'montar_cofrinhos'.

    Cofrinhos fora do formato são descartados individualmente, para que um
    cofrinho corrompido não leve a conta inteira embora.
    """
    cofrinhos = {}
    if not texto.strip():
        return cofrinhos

    for pedaco in texto.split(SEPARADOR_DE_COFRINHO):
        campos = pedaco.split(SEPARADOR_INTERNO)
        if len(campos) != 3:
            continue
        nome, saldo, taxa = campos
        try:
            cofrinhos[nome.strip()] = {
                "saldo": float(saldo),
                "taxa_mensal": float(taxa),
            }
        except ValueError:
            continue
    return cofrinhos


def montar_linha(conta):
    """Monta a linha de texto que representa uma conta."""
    dados = conta.para_dicionario()
    cliente = dados["cliente"]
    cartao = dados["cartao"]

    valores = {
        "numero": limpar_texto(dados["numero"]),
        "titular": limpar_texto(cliente["nome"]),
        "cpf": limpar_texto(cliente["cpf"]),
        "email": limpar_texto(cliente["email"]),
        "telefone": limpar_texto(cliente["telefone"]),
        "chave_pix": limpar_texto(dados["chave_pix"]),
        "salt": dados["salt"],
        "pin_hash": dados["pin_hash"],
        "bloqueada": str(dados["bloqueada"]),
        "tentativas": str(dados["tentativas_falhas"]),
        "saldo": f"{dados['saldo']:.2f}",
        "limite": f"{dados['limite']:.2f}",
        "limite_cartao": f"{cartao['limite']:.2f}",
        "fatura_cartao": f"{cartao['saldo']:.2f}",
        "cartao_numero": cartao["numero"],
        "cartao_validade": cartao["validade"],
        "cartao_dia_pagamento": str(cartao["data_pagamento"]),
        "cartao_salt_cvv": cartao["salt_cvv"],
        "cartao_hash_cvv": cartao["hash_cvv"],
        "cartao_total_pago": f"{cartao['total_pago']:.2f}",
        "cartao_parcelas": str(cartao["parcelas"]),
        # Com mais casas: a parcela vezes a quantidade precisa bater com o total
        "cartao_valor_parcela": f"{cartao['valor_parcela']:.6f}",
        "divida_emprestimo": f"{dados['divida_emprestimo']:.2f}",
        "dolar": f"{dados['saldo_dolar']:.2f}",
        "euro": f"{dados['saldo_euro']:.2f}",
        "yuan": f"{dados['saldo_yuan']:.2f}",
        "bytepoints": f"{dados['bytepoints']:.2f}",
        "cofrinhos": montar_cofrinhos(dados["cofrinhos"]),
    }
    return SEPARADOR_DE_CAMPO.join(valores[coluna] for coluna in COLUNAS)


def ler_linha(linha):
    """Reconstrói uma ContaCorrente a partir de uma linha do arquivo.

    Devolve None quando a linha está vazia, é comentário ou está fora do
    formato — assim um arquivo parcialmente corrompido ainda recupera as
    contas que estão íntegras, em vez de derrubar o sistema no boot.
    """
    linha_limpa = linha.strip()
    if not linha_limpa or linha_limpa.startswith(MARCA_DE_COMENTARIO):
        return None

    campos = linha_limpa.split(SEPARADOR_DE_CAMPO)
    colunas = FORMATOS_POR_QUANTIDADE.get(len(campos))
    if colunas is None:
        return None

    # zip junta cada nome de coluna ao seu valor: {"numero": "0001", ...}
    bruto = {coluna: valor.strip() for coluna, valor in zip(colunas, campos)}

    try:
        dados = {
            "numero": bruto["numero"],
            "cliente": {
                "nome": bruto["titular"],
                "cpf": bruto["cpf"],
                "email": bruto.get("email", ""),
                "telefone": bruto.get("telefone", ""),
            },
            "chave_pix": bruto["chave_pix"],
            "salt": bruto["salt"],
            "pin_hash": bruto["pin_hash"],
            "bloqueada": bruto["bloqueada"] == "True",
            "tentativas_falhas": int(bruto["tentativas"]),
            "saldo": float(bruto["saldo"]),
            "limite": float(bruto.get("limite", "0")),
            "limite_cartao_credito": float(bruto["limite_cartao"]),
            "fatura_cartao_credito": float(bruto["fatura_cartao"]),
            "divida_emprestimo": float(bruto["divida_emprestimo"]),
            "saldo_dolar": float(bruto["dolar"]),
            "saldo_euro": float(bruto["euro"]),
            "saldo_yuan": float(bruto["yuan"]),
            "bytepoints": float(bruto["bytepoints"]),
            "cofrinhos": ler_cofrinhos(bruto["cofrinhos"]),
        }
        if "cartao_numero" in bruto:
            dados["cartao"] = {
                "nome": bruto["titular"],
                "numero": bruto["cartao_numero"],
                "validade": bruto["cartao_validade"],
                "data_pagamento": int(bruto["cartao_dia_pagamento"]),
                "salt_cvv": bruto["cartao_salt_cvv"],
                "hash_cvv": bruto["cartao_hash_cvv"],
                "limite": float(bruto["limite_cartao"]),
                "saldo": float(bruto["fatura_cartao"]),
                "total_pago": float(bruto["cartao_total_pago"]),
                "parcelas": int(bruto["cartao_parcelas"]),
                "valor_parcela": float(bruto["cartao_valor_parcela"]),
            }
        # A própria classe se reconstrói e valida (CPF, saldo não negativo)
        return ContaCorrente.de_dicionario(dados)
    except (ValueError, TypeError):
        # Número que não é número, CPF malformado, saldo negativo...
        return None


def salvar_contas_txt(contas, caminho=ARQUIVO_CONTAS):
    """Grava a lista de contas no arquivo de texto. (Projeto 1)

    Executada automaticamente ao encerrar o sistema. O modo 'w' cria o
    arquivo na primeira vez e sobrescreve nas seguintes, de modo que o
    arquivo sempre reflete o estado atual do banco.

    Devolve True quando a gravação foi concluída.
    """
    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(CABECALHO + "\n")
            for conta in contas:
                arquivo.write(montar_linha(conta) + "\n")
        return True
    except OSError:
        return False


def carregar_contas_txt_detalhado(caminho=ARQUIVO_CONTAS):
    """Lê o arquivo e devolve (contas, linhas_ignoradas).

    A leitura usa 'for linha in arquivo', que traz uma linha por vez em vez de
    carregar o arquivo inteiro na memória.
    """
    contas = []
    ignoradas = 0

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                if not linha.strip() or linha.strip().startswith(MARCA_DE_COMENTARIO):
                    continue  # linha em branco ou cabeçalho: não é erro
                conta = ler_linha(linha)
                if conta is None:
                    ignoradas += 1
                    continue
                contas.append(conta)
    except FileNotFoundError:
        # Primeira execução do sistema: ainda não existe arquivo para ler
        return [], 0
    except (OSError, UnicodeDecodeError):
        return [], 0

    return contas, ignoradas


def carregar_contas_txt(caminho=ARQUIVO_CONTAS):
    """Lê as contas do arquivo de texto e devolve a lista. (Projeto 1)

    Executada no boot do sistema para restaurar os saldos em memória.
    Devolve lista vazia quando o arquivo não existe — é o caso da primeira
    execução, tratado como situação normal e não como erro.
    """
    contas, _ = carregar_contas_txt_detalhado(caminho)
    return contas


def resumo_do_carregamento(contas, ignoradas, caminho=ARQUIVO_CONTAS):
    """Monta a mensagem que o main exibe no boot."""
    if not contas and not ignoradas:
        return f"Nenhum arquivo '{caminho}' encontrado."

    mensagem = f"{len(contas)} conta(s) lida(s) de '{caminho}'."
    if ignoradas:
        mensagem += f" {ignoradas} linha(s) ignorada(s) por estarem fora do formato."
    return mensagem


def conferir_saldos(contas_txt, contas_memoria):
    """Compara os saldos do TXT com os das contas carregadas do JSON.

    Os dois arquivos são gravados no mesmo encerramento, então devem contar a
    mesma história. Uma divergência significa que um dos arquivos foi editado
    à mão ou que uma gravação falhou — vale avisar em vez de seguir calado.

    Devolve a lista de divergências encontradas (vazia quando tudo confere).
    """
    saldos_em_memoria = {conta.numero: conta.saldo for conta in contas_memoria}
    divergencias = []

    for conta in contas_txt:
        if conta.numero not in saldos_em_memoria:
            divergencias.append(f"conta {conta.numero} existe no TXT mas não no JSON")
        elif abs(saldos_em_memoria[conta.numero] - conta.saldo) > 0.005:
            divergencias.append(
                f"conta {conta.numero}: TXT={conta.saldo:.2f} "
                f"JSON={saldos_em_memoria[conta.numero]:.2f}"
            )

    numeros_no_txt = {conta.numero for conta in contas_txt}
    for numero in saldos_em_memoria:
        if numero not in numeros_no_txt:
            divergencias.append(f"conta {numero} existe no JSON mas não no TXT")

    return divergencias


if __name__ == "__main__":
    # Teste de ida e volta: grava contas em um arquivo, lê de novo e confere.
    ARQUIVO_DE_TESTE = "contas_teste.txt"

    originais = [
        ContaCorrente(numero="9001",
                      cliente=Cliente("Teste, da Silva", "999.999.999-99",
                                      email="teste@email.com",
                                      telefone="(81) 99999-0000"),
                      chave_pix="teste@email.com", pin="4321", saldo=1234.56,
                      limite_cartao_credito=2000.00, saldo_dolar=10.50,
                      cofrinhos_iniciais={"Reserva": (300.00, 0.005)}),
        ContaCorrente(numero="9002",
                      cliente=Cliente("Sem Cofrinho", "888.888.888-88"),
                      chave_pix="sem@email.com", pin="1234", saldo=0.0),
    ]
    # Os atributos são privados: dívida e pontos são gerados por operações de
    # verdade, e não por atribuição direta.
    originais[0].contratar_emprestimo(500.00, 10)   # gera dívida
    originais[0].sacar(42.50)                       # gera BytePoints

    salvar_contas_txt(originais, ARQUIVO_DE_TESTE)
    recuperadas, ignoradas = carregar_contas_txt_detalhado(ARQUIVO_DE_TESTE)

    print(f"Gravadas: {len(originais)} | Lidas: {len(recuperadas)} | "
          f"Ignoradas: {ignoradas}\n")

    for antes, depois in zip(originais, recuperadas):
        print(f"Conta {depois.numero} - {depois.titular}")
        print(f"  cliente .....: {depois.cliente!r} | {depois.cliente.email or '-'} "
              f"| {depois.cliente.telefone or '-'}")
        print(f"  saldo .......: {antes.saldo:.2f} -> {depois.saldo:.2f}")
        print(f"  divida ......: {antes.divida_emprestimo:.2f} -> "
              f"{depois.divida_emprestimo:.2f}")
        print(f"  bytepoints ..: {antes.bytepoints:.2f} -> {depois.bytepoints:.2f}")
        print(f"  cofrinhos ...: {depois.cofrinhos}")
        pin_original = "4321" if antes.numero == "9001" else "1234"
        print(f"  PIN confere .: {depois.confere_pin(pin_original)}")
        print()

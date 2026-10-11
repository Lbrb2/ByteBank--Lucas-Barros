"""Persistência das contas em arquivo de texto puro (Projeto 1 - Aula 7).

Este módulo cumpre o Projeto 1 da Aula 7: gravar e recuperar as contas em um
arquivo .txt usando apenas as técnicas da aula — 'with open', 'write',
'for linha in arquivo', '.strip()' e '.split()'. Nenhuma biblioteca de
serialização é usada aqui: a montagem e a quebra de cada linha são manuais.

Formato de 'contas.txt' — uma conta por linha, campos separados por vírgula:

    numero,titular,cpf,chave_pix,salt,pin_hash,bloqueada,tentativas,
    saldo,limite_cartao,fatura_cartao,divida_emprestimo,
    dolar,euro,yuan,bytepoints,cofrinhos

O último campo guarda os cofrinhos, que são um dicionário aninhado. Como um
arquivo CSV é plano, eles recebem separadores próprios:

    Reserva:5000.00:0.005;Viagem:1200.00:0.007
    └──┬──┘ └───┬───┘ └─┬─┘
     nome    saldo    taxa mensal      (contas separadas por ';')

Por isso os textos gravados passam por 'limpar_texto': uma vírgula no nome do
titular, ou um ';' no nome de um cofrinho, quebraria a leitura da linha.

Relação com 'persistencia.py' (JSON): este módulo guarda o estado financeiro
das contas, que é o que o Projeto 1 pede. O extrato (pilha de transações) e os
consentimentos de Open Banking são estruturas aninhadas e profundas, que só o
JSON armazena. Os dois arquivos são gravados ao encerrar o sistema e ambos
são lidos no boot — veja 'main.py'.
"""

from conta import Conta

ARQUIVO_CONTAS = "contas.txt"

SEPARADOR_DE_CAMPO = ","
SEPARADOR_DE_COFRINHO = ";"
SEPARADOR_INTERNO = ":"
MARCA_DE_COMENTARIO = "#"

CABECALHO = (
    "# numero,titular,cpf,chave_pix,salt,pin_hash,bloqueada,tentativas,"
    "saldo,limite_cartao,fatura_cartao,divida_emprestimo,"
    "dolar,euro,yuan,bytepoints,cofrinhos"
)

# Quantidade de campos de uma linha completa. Serve de validação na leitura:
# linha com outro número de campos está corrompida e é ignorada.
TOTAL_DE_CAMPOS = 17

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
    campos = [
        limpar_texto(conta.numero),
        limpar_texto(conta.titular),
        limpar_texto(conta.cpf),
        limpar_texto(conta.chave_pix),
        conta.salt,
        conta.pin_hash,
        str(conta.bloqueada),
        str(conta.tentativas_falhas),
        f"{conta.saldo:.2f}",
        f"{conta.limite_cartao_credito:.2f}",
        f"{conta.fatura_cartao_credito:.2f}",
        f"{conta.divida_emprestimo:.2f}",
        f"{conta.saldo_dolar:.2f}",
        f"{conta.saldo_euro:.2f}",
        f"{conta.saldo_yuan:.2f}",
        f"{conta.bytepoints:.2f}",
        montar_cofrinhos(conta.cofrinhos),
    ]
    return SEPARADOR_DE_CAMPO.join(campos)


def ler_linha(linha):
    """Reconstrói uma Conta a partir de uma linha do arquivo.

    Devolve None quando a linha está vazia, é comentário ou está fora do
    formato — assim um arquivo parcialmente corrompido ainda recupera as
    contas que estão íntegras, em vez de derrubar o sistema no boot.
    """
    linha_limpa = linha.strip()
    if not linha_limpa or linha_limpa.startswith(MARCA_DE_COMENTARIO):
        return None

    campos = linha_limpa.split(SEPARADOR_DE_CAMPO)
    if len(campos) != TOTAL_DE_CAMPOS:
        return None

    try:
        conta = Conta(
            numero=campos[0].strip(),
            titular=campos[1].strip(),
            cpf=campos[2].strip(),
            chave_pix=campos[3].strip(),
            saldo=float(campos[8]),
            limite_cartao_credito=float(campos[9]),
            saldo_dolar=float(campos[12]),
            saldo_euro=float(campos[13]),
            saldo_yuan=float(campos[14]),
        )
    except ValueError:
        # Algum campo numérico não era número
        return None

    # O construtor gera salt e hash novos a partir do PIN padrão; aqui os
    # valores gravados são restaurados para que o PIN do cliente continue valendo.
    conta.salt = campos[4].strip()
    conta.pin_hash = campos[5].strip()
    conta.bloqueada = campos[6].strip() == "True"

    try:
        conta.tentativas_falhas = int(campos[7])
        conta.fatura_cartao_credito = float(campos[10])
        conta.divida_emprestimo = float(campos[11])
        conta.bytepoints = float(campos[15])
    except ValueError:
        return None

    conta.cofrinhos = ler_cofrinhos(campos[16])
    return conta


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
        Conta(numero="9001", titular="Teste, da Silva", cpf="999.999.999-99",
              chave_pix="teste@email.com", pin="4321", saldo=1234.56,
              limite_cartao_credito=2000.00, saldo_dolar=10.50,
              cofrinhos_iniciais={"Reserva": (300.00, 0.005)}),
        Conta(numero="9002", titular="Sem Cofrinho", cpf="888.888.888-88",
              chave_pix="sem@email.com", pin="1234", saldo=0.0),
    ]
    originais[0].divida_emprestimo = 500.00
    originais[0].bytepoints = 42.5

    salvar_contas_txt(originais, ARQUIVO_DE_TESTE)
    recuperadas, ignoradas = carregar_contas_txt_detalhado(ARQUIVO_DE_TESTE)

    print(f"Gravadas: {len(originais)} | Lidas: {len(recuperadas)} | "
          f"Ignoradas: {ignoradas}\n")

    for antes, depois in zip(originais, recuperadas):
        print(f"Conta {depois.numero} - {depois.titular}")
        print(f"  saldo .......: {antes.saldo:.2f} -> {depois.saldo:.2f}")
        print(f"  divida ......: {antes.divida_emprestimo:.2f} -> "
              f"{depois.divida_emprestimo:.2f}")
        print(f"  bytepoints ..: {antes.bytepoints:.2f} -> {depois.bytepoints:.2f}")
        print(f"  cofrinhos ...: {depois.cofrinhos}")
        pin_original = "4321" if antes.numero == "9001" else "1234"
        print(f"  PIN confere .: {depois.confere_pin(pin_original)}")
        print()

"""ByteBank - Sistema bancário FinTech
Projeto Avaliativo AV2 | BD015 - Algoritmo e Estrutura de Dados | CESAR School

Ponto de entrada do sistema. Execute com: python main.py
"""

from banco import Banco
from conta import Conta
from interface import Interface
from open_banking import InstituicaoParceira
import persistencia
import persistencia_txt


def carregar_contas_ficticias(banco):
    """Cadastra as contas de demonstração usadas para testar o sistema."""
    banco.adicionar_conta(Conta(
        numero="0001", titular="Amanda Silva", cpf="111.111.111-11",
        chave_pix="amanda@email.com", pin="1111", saldo=1000.00,
        limite_cartao_credito=4000.00,
        saldo_dolar=200.00, saldo_euro=150.00, saldo_yuan=1000.00,
        cofrinhos_iniciais={"Reserva": (5000.00, 0.005), "Viagem": (1200.00, 0.007)}
    ))
    banco.adicionar_conta(Conta(
        numero="0002", titular="Caio Ferreira", cpf="222.222.222-22",
        chave_pix="caio@email.com", pin="2222", saldo=2500.50,
        limite_cartao_credito=2500.00,
        saldo_dolar=300.00, saldo_euro=200.00, saldo_yuan=1500.00,
        cofrinhos_iniciais={"Reserva": (3000.00, 0.005)}
    ))
    banco.adicionar_conta(Conta(
        numero="0003", titular="Douglas Alves", cpf="333.333.333-33",
        chave_pix="douglas@email.com", pin="3333", saldo=320.00,
        limite_cartao_credito=3000.00,
        saldo_dolar=100.00, saldo_euro=80.00, saldo_yuan=500.00,
        cofrinhos_iniciais={"Emergência": (1000.00, 0.006)}
    ))
    return banco


def carregar_instituicoes_parceiras(banco):
    """Cadastra as instituições fictícias do Open Banking.

    Os clientes são identificados pelo CPF, que é a chave de ligação entre
    as instituições — igual ao Open Finance real.
    """
    banco.diretorio.adicionar(InstituicaoParceira(
        "BNC01", "Banco Nacional", {
            "111.111.111-11": {"saldo": 3200.00, "investimentos": 12000.00},
            "222.222.222-22": {"saldo": 800.00, "investimentos": 0.00},
        }
    ))
    banco.diretorio.adicionar(InstituicaoParceira(
        "FIN02", "FinPlus Investimentos", {
            "111.111.111-11": {"saldo": 450.00, "investimentos": 28000.00},
            "333.333.333-33": {"saldo": 150.00, "investimentos": 2200.00},
        }
    ))
    banco.diretorio.adicionar(InstituicaoParceira(
        "COP03", "Cooperativa Crédito Sul", {
            "222.222.222-22": {"saldo": 5400.00, "investimentos": 1500.00},
        }
    ))
    return banco


def montar_banco_a_partir_das_contas(contas):
    """Cria um banco já populado com as contas lidas do arquivo de texto."""
    banco = Banco("ByteBank")
    for conta in contas:
        banco.adicionar_conta(conta)
    carregar_instituicoes_parceiras(banco)
    return banco


def dar_boot():
    """Restaura o estado do banco a partir dos arquivos em disco.

    São lidas as duas fontes de persistência:

      - 'contas.txt'  -> contas e saldos (Projeto 1 da Aula 7)
      - 'dados_bytebank.json' -> estado completo, incluindo o extrato de
        transações e os consentimentos de Open Banking, que são estruturas
        aninhadas e não cabem em um CSV plano.

    Quando os dois existem, o JSON é usado porque contém tudo o que o TXT
    contém e mais; o TXT então serve de conferência independente dos saldos.
    Quando só o TXT existe, ele reconstrói o banco sozinho. Sem nenhum dos
    dois, o sistema sobe com as contas de demonstração.

    Devolve o banco pronto para uso.
    """
    contas_txt, ignoradas = persistencia_txt.carregar_contas_txt_detalhado()
    print(persistencia_txt.resumo_do_carregamento(contas_txt, ignoradas))

    banco, mensagem_json = persistencia.carregar()

    if banco is not None:
        print(mensagem_json)
        divergencias = persistencia_txt.conferir_saldos(contas_txt, banco.contas)
        for divergencia in divergencias:
            print(f"[AVISO] Divergência entre os arquivos: {divergencia}")
        print()
        return banco

    if contas_txt:
        print("Estado reconstruído a partir do arquivo de texto.\n")
        return montar_banco_a_partir_das_contas(contas_txt)

    print(f"{mensagem_json} Iniciando com as contas de demonstração.\n")
    banco = carregar_contas_ficticias(Banco("ByteBank"))
    carregar_instituicoes_parceiras(banco)
    return banco


def encerrar(banco):
    """Grava o estado do banco nos dois arquivos antes de o programa sair."""
    if persistencia_txt.salvar_contas_txt(banco.contas):
        print(f"{len(banco.contas)} conta(s) gravada(s) em "
              f"'{persistencia_txt.ARQUIVO_CONTAS}'.")
    else:
        print(f"[ERRO] Não foi possível gravar "
              f"'{persistencia_txt.ARQUIVO_CONTAS}'.")

    sucesso, mensagem = persistencia.salvar(banco)
    print(mensagem)


def main():
    banco = dar_boot()

    # O 'finally' garante que a gravação aconteça mesmo se o programa for
    # interrompido no meio (Ctrl+C, Ctrl+D ou um erro inesperado). Sem ele, a
    # gravação só ocorreria na saída pelo menu, e qualquer interrupção
    # devolveria o sistema à amnésia que a persistência existe para curar.
    try:
        Interface(banco).executar()
    except (KeyboardInterrupt, EOFError):
        print("\n\n[AVISO] Execução interrompida. Salvando os dados...")
    finally:
        encerrar(banco)


if __name__ == "__main__":
    main()

"""ByteBank - Sistema bancário FinTech
Projeto Avaliativo AV2 | BD015 - Algoritmo e Estrutura de Dados | CESAR School

Ponto de entrada do sistema. Execute com: python main.py
"""

from banco import Banco
from cliente import Cliente
from conta import ContaCorrente
from interface import Interface
from open_banking import InstituicaoParceira


def carregar_contas_ficticias(banco):
    """Cadastra as contas de demonstração usadas para testar o sistema.

    Cada conta recebe um objeto Cliente: primeiro se cria a pessoa, depois a
    conta que pertence a ela.
    """
    amanda = Cliente("Amanda Silva", "111.111.111-11",
                     email="amanda@email.com", telefone="(81) 98888-1111")
    caio = Cliente("Caio Ferreira", "222.222.222-22",
                   email="caio@email.com", telefone="(81) 98888-2222")
    douglas = Cliente("Douglas Alves", "333.333.333-33",
                      email="douglas@email.com", telefone="(81) 98888-3333")

    banco.adicionar_conta(ContaCorrente(
        numero="0001", cliente=amanda,
        chave_pix="amanda@email.com", pin="1111", saldo=1000.00, limite=500.00,
        limite_cartao_credito=4000.00,
        saldo_dolar=200.00, saldo_euro=150.00, saldo_yuan=1000.00,
        cofrinhos_iniciais={"Reserva": (5000.00, 0.005), "Viagem": (1200.00, 0.007)}
    ))
    banco.adicionar_conta(ContaCorrente(
        numero="0002", cliente=caio,
        chave_pix="caio@email.com", pin="2222", saldo=2500.50, limite=1000.00,
        limite_cartao_credito=2500.00,
        saldo_dolar=300.00, saldo_euro=200.00, saldo_yuan=1500.00,
        cofrinhos_iniciais={"Reserva": (3000.00, 0.005)}
    ))
    banco.adicionar_conta(ContaCorrente(
        numero="0003", cliente=douglas,
        chave_pix="douglas@email.com", pin="3333", saldo=320.00, limite=300.00,
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


def dar_boot():
    """Restaura o banco a partir do disco ou, na primeira execução, cria o
    banco com as contas de demonstração. Devolve o banco pronto para uso.

    Quem sabe ler o próprio estado é o Banco (Banco.carregar_estado); aqui só
    se decide o que fazer quando não há nada gravado.
    """
    banco, mensagem = Banco.carregar_estado()
    print(mensagem)

    if banco is None:
        print("Iniciando com as contas de demonstração.")
        banco = carregar_contas_ficticias(Banco("ByteBank"))

    # O arquivo TXT guarda só as contas. Quando o banco veio dele (ou de um
    # JSON antigo sem Open Banking), as instituições parceiras são recriadas.
    if not banco.diretorio.listar():
        carregar_instituicoes_parceiras(banco)

    print()
    return banco


def encerrar(banco):
    """Pede ao Banco que salve o próprio estado antes de o programa sair."""
    _, mensagem = banco.salvar_estado()
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

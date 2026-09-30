"""ByteBank - Sistema bancário FinTech
Projeto Avaliativo AV2 | BD015 - Algoritmo e Estrutura de Dados | CESAR School

Ponto de entrada do sistema. Execute com: python main.py
"""

from banco import Banco
from conta import Conta
from interface import Interface
from open_banking import InstituicaoParceira
import persistencia


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


def main():
    banco, mensagem = persistencia.carregar()
    if banco is None:
        # Primeira execução (ou arquivo ilegível): começa com os dados de demonstração
        banco = carregar_contas_ficticias(Banco("ByteBank"))
        carregar_instituicoes_parceiras(banco)
        print(f"{mensagem} Iniciando com as contas de demonstração.\n")
    else:
        print(f"{mensagem}\n")

    Interface(banco).executar()

    sucesso, mensagem = persistencia.salvar(banco)
    print(mensagem)


if __name__ == "__main__":
    main()

from django.test import SimpleTestCase

from demandas.cpf import contem_cpf, cpf_valido
from demandas.models import Status
from demandas.transicoes import destinos_permitidos, transicao_permitida


class TransicoesTests(SimpleTestCase):
    ABERTOS = [Status.NOVA, Status.A_FAZER, Status.EM_ANDAMENTO, Status.AGUARDANDO]
    FECHADOS = [Status.CONCLUIDA, Status.CANCELADA]

    def test_nada_volta_para_nova(self):
        for atual in Status:
            self.assertFalse(transicao_permitida(atual, Status.NOVA), atual)

    def test_entre_abertas_qualquer_mudanca_exceto_nova(self):
        for atual in self.ABERTOS:
            for novo in self.ABERTOS:
                esperado = novo not in (atual, Status.NOVA)
                self.assertEqual(transicao_permitida(atual, novo), esperado, (atual, novo))

    def test_aberta_pode_fechar(self):
        for atual in self.ABERTOS:
            for novo in self.FECHADOS:
                self.assertTrue(transicao_permitida(atual, novo), (atual, novo))

    def test_fechada_so_reabre_para_a_fazer(self):
        for atual in self.FECHADOS:
            self.assertEqual(destinos_permitidos(atual), [Status.A_FAZER], atual)

    def test_mesmo_status_nao_e_transicao(self):
        self.assertFalse(transicao_permitida(Status.A_FAZER, Status.A_FAZER))


class CpfTests(SimpleTestCase):
    # CPFs gerados apenas para teste (dígitos verificadores válidos, sem titular real conhecido).
    VALIDO = "529.982.247-25"

    def test_cpf_valido_com_pontuacao(self):
        self.assertTrue(contem_cpf(f"Cliente com CPF {self.VALIDO} ligou"))

    def test_cpf_valido_sem_pontuacao(self):
        self.assertTrue(contem_cpf("cpf 52998224725 no texto"))

    def test_digito_verificador_invalido(self):
        self.assertFalse(contem_cpf("529.982.247-26"))
        self.assertFalse(cpf_valido("52998224726"))

    def test_sequencia_repetida_nao_conta(self):
        self.assertFalse(contem_cpf("111.111.111-11"))
        self.assertFalse(contem_cpf("00000000000"))

    def test_numero_de_telefone_nao_conta(self):
        self.assertFalse(contem_cpf("Ligar para (11) 98765-4321"))
        self.assertFalse(contem_cpf("Ligar para 11987654321"))

    def test_digitos_colados_nao_formam_cpf(self):
        self.assertFalse(contem_cpf("protocolo 1529982247251"))

    def test_varios_textos(self):
        self.assertTrue(contem_cpf("sem nada", "", self.VALIDO))
        self.assertFalse(contem_cpf("", None))

from datetime import UTC, date, datetime, timedelta

from django.test import TestCase
from django.urls import reverse

from core import relogio
from core.testes import AGORA_PADRAO, criar_usuario
from demandas import services as demandas_services
from demandas.models import Prioridade, Status
from painel import selectors, services
from painel.models import FocoDoDia

DIA = date(2026, 10, 19)
# Horários-limite em São Paulo (UTC-3), expressos em UTC.
AS_23H30_DO_DIA_19 = datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
AS_00H30_DO_DIA_20 = datetime(2026, 10, 20, 3, 30, tzinfo=UTC)


class PainelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = criar_usuario()

    def criar(self, titulo="Demanda", **campos):
        with relogio.congelar(AGORA_PADRAO):
            return demandas_services.criar_demanda(self.usuario, titulo=titulo, **campos)

    def titulos(self, demandas):
        return [d.titulo for d in demandas]


class HorariosLimiteTests(PainelTestCase):
    def test_as_23h30_prazo_de_hoje_vence_hoje_e_nao_esta_atrasado(self):
        self.criar("Prazo 19", prazo=DIA)
        self.criar("Prazo 18", prazo=DIA - timedelta(days=1))
        with relogio.congelar(AS_23H30_DO_DIA_19):
            painel = selectors.painel_do_dia(self.usuario)
            self.assertEqual(self.titulos(painel["vencem_hoje"]), ["Prazo 19"])
            self.assertEqual(self.titulos(painel["atrasadas"]), ["Prazo 18"])

    def test_as_00h30_o_prazo_de_ontem_ja_esta_atrasado(self):
        self.criar("Prazo 19", prazo=DIA)
        self.criar("Prazo 20", prazo=DIA + timedelta(days=1))
        with relogio.congelar(AS_00H30_DO_DIA_20):
            painel = selectors.painel_do_dia(self.usuario)
            self.assertEqual(self.titulos(painel["vencem_hoje"]), ["Prazo 20"])
            self.assertEqual(self.titulos(painel["atrasadas"]), ["Prazo 19"])

    def test_concluidas_hoje_usa_o_dia_local(self):
        demanda = self.criar("Concluída às 23h30")
        with relogio.congelar(AS_23H30_DO_DIA_19):
            demandas_services.mudar_status(demanda, Status.CONCLUIDA)
            self.assertEqual(
                self.titulos(selectors.painel_do_dia(self.usuario)["concluidas_hoje"]),
                ["Concluída às 23h30"],
            )
        with relogio.congelar(AS_00H30_DO_DIA_20):
            self.assertEqual(list(selectors.painel_do_dia(self.usuario)["concluidas_hoje"]), [])


class BlocosEOrdenacaoTests(PainelTestCase):
    def test_ordenacao_padrao(self):
        self.criar("Baixa sem prazo", prioridade=Prioridade.BAIXA)
        self.criar("Alta com prazo longe", prioridade=Prioridade.ALTA, prazo=DIA + timedelta(5))
        self.criar("Média com prazo perto", prazo=DIA + timedelta(1))
        self.criar("Atrasada recente", prioridade=Prioridade.BAIXA, prazo=DIA - timedelta(1))
        self.criar("Atrasada antiga", prioridade=Prioridade.BAIXA, prazo=DIA - timedelta(9))
        self.criar("Alta sem prazo", prioridade=Prioridade.ALTA)
        with relogio.congelar(AGORA_PADRAO):
            ordem = self.titulos(selectors.candidatas_ao_top(self.usuario))
        self.assertEqual(
            ordem,
            [
                "Atrasada antiga",
                "Atrasada recente",
                "Alta com prazo longe",
                "Alta sem prazo",
                "Média com prazo perto",
                "Baixa sem prazo",
            ],
        )

    def test_blocos_do_painel(self):
        self.criar("Na caixa")
        self.criar("Próxima semana", status=Status.A_FAZER, prazo=DIA + timedelta(days=7))
        self.criar("Longe", status=Status.A_FAZER, prazo=DIA + timedelta(days=8))
        self.criar("Sem prazo", status=Status.A_FAZER)
        aguardando = self.criar("Aguardando", status=Status.AGUARDANDO, aguardando_quem="Banco")
        with relogio.congelar(AGORA_PADRAO + timedelta(days=3)):
            painel = selectors.painel_do_dia(self.usuario)
            resposta = self.client_get_painel()
        self.assertEqual(self.titulos(painel["caixa"]), ["Na caixa"])
        self.assertEqual(painel["sem_prazo"], 3)  # caixa, sem prazo e aguardando
        self.assertEqual(painel["total_abertas"], 5)
        self.assertEqual(list(painel["aguardando"]), [aguardando])
        self.assertContains(resposta, "Hora de cobrar")
        self.assertContains(resposta, "há 3 dias")

    def test_proximos_7_dias(self):
        self.criar("Daqui a 7", status=Status.A_FAZER, prazo=DIA + timedelta(days=7))
        self.criar("Daqui a 8", status=Status.A_FAZER, prazo=DIA + timedelta(days=8))
        with relogio.congelar(AGORA_PADRAO):
            self.assertEqual(
                self.titulos(selectors.painel_do_dia(self.usuario)["proximos"]), ["Daqui a 7"]
            )

    def test_caixa_vazia_mostra_mensagem_amigavel(self):
        self.assertContains(self.client_get_painel(), "Caixa de entrada zerada. Bom trabalho!")

    def client_get_painel(self):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("painel:inicio"))


class TopDoDiaTests(PainelTestCase):
    def setUp(self):
        self.enterContext(relogio.congelar(AGORA_PADRAO))
        self.demandas = [self.criar(f"D{n}") for n in range(1, 6)]

    def test_quarto_item_e_rejeitado(self):
        for demanda in self.demandas[:3]:
            services.adicionar_ao_top(self.usuario, demanda)
        with self.assertRaisesMessage(services.ErroDoTop, "já está completo"):
            services.adicionar_ao_top(self.usuario, self.demandas[3])
        self.assertEqual(FocoDoDia.objects.count(), 3)

    def test_mesma_demanda_duas_vezes(self):
        services.adicionar_ao_top(self.usuario, self.demandas[0])
        with self.assertRaisesMessage(services.ErroDoTop, "já está no Top 3"):
            services.adicionar_ao_top(self.usuario, self.demandas[0])

    def test_demanda_fechada_nao_entra(self):
        concluida = demandas_services.mudar_status(self.demandas[0], Status.CONCLUIDA)
        with self.assertRaises(services.ErroDoTop):
            services.adicionar_ao_top(self.usuario, concluida)

    def test_posicao_liberada_e_reaproveitada(self):
        focos = [services.adicionar_ao_top(self.usuario, d) for d in self.demandas[:3]]
        services.remover_do_top(self.usuario, focos[1].pk)
        novo = services.adicionar_ao_top(self.usuario, self.demandas[3])
        self.assertEqual(novo.ordem, 2)

    def test_trazer_pendentes_do_ultimo_top(self):
        ontem = AGORA_PADRAO - timedelta(days=2)  # o "último" Top 3 pode ser de dias atrás
        with relogio.congelar(ontem):
            for demanda in self.demandas[:3]:
                services.adicionar_ao_top(self.usuario, demanda)
        demandas_services.mudar_status(self.demandas[1], Status.CONCLUIDA)
        services.adicionar_ao_top(self.usuario, self.demandas[4])

        trazidos = services.trazer_pendentes(self.usuario)

        self.assertEqual(trazidos, 2)
        hoje = [f.demanda.titulo for f in selectors.top_de_hoje(self.usuario)]
        self.assertEqual(hoje, ["D5", "D1", "D3"])  # escolha de hoje mantida; pendentes na ordem

    def test_trazer_pendentes_sem_top_anterior(self):
        self.assertEqual(services.trazer_pendentes(self.usuario), 0)

    def test_telas_do_top(self):
        self.client.force_login(self.usuario)
        self.client.post(reverse("painel:top_adicionar"), {"demanda": self.demandas[0].pk})
        self.assertEqual(FocoDoDia.objects.count(), 1)
        self.client.post(reverse("painel:top_adicionar"), {"demanda": "abc"})
        self.assertEqual(FocoDoDia.objects.count(), 1)
        alheia = demandas_services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        resposta = self.client.post(reverse("painel:top_adicionar"), {"demanda": alheia.pk})
        self.assertEqual(resposta.status_code, 404)

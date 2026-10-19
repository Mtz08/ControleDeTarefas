from datetime import UTC, date, datetime, timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core import relogio
from core.testes import AGORA_PADRAO, criar_usuario
from demandas import services as demandas_services
from demandas.models import Origem, Status
from painel import indicadores, selectors
from painel.forms import PeriodoForm, mes_inteiro
from painel.indicadores import Conclusao


class IndicadoresTests(SimpleTestCase):
    def test_percentual_no_prazo_ignora_sem_prazo(self):
        conclusoes = [
            Conclusao(
                date(2026, 10, 1), date(2026, 10, 5), date(2026, 10, 5)
            ),  # no limite: no prazo
            Conclusao(date(2026, 10, 1), date(2026, 10, 6), date(2026, 10, 5)),  # atrasou
            Conclusao(date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 9)),  # no prazo
            Conclusao(date(2026, 10, 1), date(2026, 10, 3), None),  # sem prazo
        ]
        resultado = indicadores.no_prazo(conclusoes)
        self.assertEqual((resultado.com_prazo, resultado.no_prazo, resultado.sem_prazo), (3, 2, 1))
        self.assertEqual(resultado.percentual, 66.7)

    def test_percentual_sem_nenhum_prazo(self):
        self.assertIsNone(indicadores.no_prazo([]).percentual)

    def test_media_e_mediana_em_dias_corridos(self):
        conclusoes = [
            Conclusao(date(2026, 10, 1), date(2026, 10, 1), None),  # 0 dias
            Conclusao(date(2026, 10, 1), date(2026, 10, 3), None),  # 2 dias
            Conclusao(date(2026, 10, 1), date(2026, 10, 11), None),  # 10 dias
        ]
        tempo = indicadores.tempo_de_conclusao(conclusoes)
        self.assertEqual((tempo.media, tempo.mediana), (4.0, 2.0))

    def test_mediana_com_quantidade_par(self):
        conclusoes = [
            Conclusao(date(2026, 10, 1), date(2026, 10, 2), None),
            Conclusao(date(2026, 10, 1), date(2026, 10, 4), None),
        ]
        self.assertEqual(indicadores.tempo_de_conclusao(conclusoes).mediana, 2.0)

    def test_semanas_de_segunda_a_domingo(self):
        semanas = indicadores.semanas(
            date(2026, 10, 1),
            date(2026, 10, 31),
            recebidas=[date(2026, 10, 1), date(2026, 10, 4), date(2026, 10, 5)],
            concluidas=[date(2026, 10, 31)],
        )
        self.assertEqual(semanas[0].inicio, date(2026, 9, 28))  # segunda-feira
        self.assertEqual(semanas[0].fim, date(2026, 10, 4))  # domingo
        self.assertEqual(semanas[0].recebidas, 2)
        self.assertEqual(semanas[1].recebidas, 1)
        self.assertEqual(semanas[-1].concluidas, 1)
        self.assertEqual(len(semanas), 5)

    def test_mes_inteiro(self):
        self.assertEqual(mes_inteiro(date(2026, 2, 1)), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(mes_inteiro(date(2026, 12, 1)), (date(2026, 12, 1), date(2026, 12, 31)))


class PeriodoFormTests(SimpleTestCase):
    def test_padrao_e_o_mes_atual(self):
        with relogio.congelar(AGORA_PADRAO):
            self.assertEqual(PeriodoForm(None).periodo(), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_mes_escolhido(self):
        self.assertEqual(
            PeriodoForm({"mes": "2026-02"}).periodo(), (date(2026, 2, 1), date(2026, 2, 28))
        )

    def test_intervalo_personalizado(self):
        form = PeriodoForm({"de": "2026-10-05", "ate": "2026-10-12"})
        self.assertEqual(form.periodo(), (date(2026, 10, 5), date(2026, 10, 12)))

    def test_intervalo_invertido_e_recusado(self):
        self.assertFalse(PeriodoForm({"de": "2026-10-12", "ate": "2026-10-05"}).is_valid())


class ResumoDoPeriodoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = criar_usuario()

    def criar_e_concluir(self, recebida, concluida, prazo=None, **campos):
        with relogio.congelar(recebida):
            demanda = demandas_services.criar_demanda(
                self.usuario, titulo="X", recebida_em=recebida, prazo=prazo, **campos
            )
        with relogio.congelar(concluida):
            return demandas_services.mudar_status(demanda, Status.CONCLUIDA)

    def test_indicadores_com_dados(self):
        inicio = datetime(2026, 10, 1, 12, tzinfo=UTC)
        self.criar_e_concluir(inicio, inicio + timedelta(days=2), prazo=date(2026, 10, 3))
        self.criar_e_concluir(
            inicio, inicio + timedelta(days=6), prazo=date(2026, 10, 3), origem=Origem.EMAIL
        )
        self.criar_e_concluir(inicio, inicio + timedelta(days=1), origem=Origem.CIRCULAR)
        # Recebida em setembro, concluída em outubro: conta só como concluída.
        self.criar_e_concluir(datetime(2026, 9, 20, 12, tzinfo=UTC), inicio)

        with relogio.congelar(AGORA_PADRAO):
            resumo = selectors.resumo_do_periodo(
                self.usuario, date(2026, 10, 1), date(2026, 10, 31)
            )

        self.assertEqual(resumo.recebidas, 3)
        self.assertEqual(resumo.concluidas, 4)
        self.assertEqual((resumo.no_prazo.com_prazo, resumo.no_prazo.no_prazo), (2, 1))
        self.assertEqual(resumo.no_prazo.sem_prazo, 2)
        # Dias corridos: 2, 6, 1 e 11 → média 5,0; mediana (2 + 6) / 2 = 4,0.
        self.assertEqual((resumo.tempo.media, resumo.tempo.mediana), (5.0, 4.0))
        origens = {d.rotulo: d.quantidade for d in resumo.por_origem}
        self.assertEqual(origens, {"Outro": 1, "E-mail": 1, "Circular": 1})

    def test_tela_csv_e_impressao(self):
        self.criar_e_concluir(AGORA_PADRAO, AGORA_PADRAO)
        self.client.force_login(self.usuario)
        with relogio.congelar(AGORA_PADRAO):
            tela = self.client.get(reverse("painel:resumo"))
            csv = self.client.get(reverse("painel:resumo_csv"))
        self.assertContains(tela, "Resumo de 01/10/2026 a 31/10/2026")
        self.assertContains(tela, "data-imprimir")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        conteudo = csv.content.decode("utf-8")
        self.assertTrue(conteudo.startswith("﻿ID;Título;"))
        self.assertEqual(len(conteudo.strip().splitlines()), 2)

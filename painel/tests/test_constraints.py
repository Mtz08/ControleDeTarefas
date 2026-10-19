"""O limite do Top 3 é garantido pelo banco, não por "contar antes de inserir"."""

from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from demandas.models import Demanda
from painel.models import FocoDoDia

DIA = date(2026, 10, 19)


class TopDoDiaConstraintsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("teste", password="senha-ficticia-123")
        cls.demandas = [
            Demanda.objects.create(usuario=cls.usuario, titulo=f"Demanda {n}") for n in range(1, 5)
        ]

    def focar(self, demanda, ordem, data=DIA):
        return FocoDoDia.objects.create(
            usuario=self.usuario, data=data, ordem=ordem, demanda=demanda
        )

    def preencher_top_3(self):
        for ordem, demanda in enumerate(self.demandas[:3], start=1):
            self.focar(demanda, ordem)

    def assertRejeitadoPeloBanco(self, criar):
        with self.assertRaises(IntegrityError), transaction.atomic():
            criar()

    def test_quarto_item_com_ordem_4_e_rejeitado(self):
        self.preencher_top_3()
        self.assertRejeitadoPeloBanco(lambda: self.focar(self.demandas[3], 4))

    def test_quarto_item_reaproveitando_uma_ordem_e_rejeitado(self):
        self.preencher_top_3()
        self.assertRejeitadoPeloBanco(lambda: self.focar(self.demandas[3], 1))

    def test_ordem_zero_e_rejeitada(self):
        self.assertRejeitadoPeloBanco(lambda: self.focar(self.demandas[0], 0))

    def test_mesma_demanda_duas_vezes_no_dia_e_rejeitada(self):
        self.focar(self.demandas[0], 1)
        self.assertRejeitadoPeloBanco(lambda: self.focar(self.demandas[0], 2))

    def test_outro_dia_tem_seu_proprio_top_3(self):
        self.preencher_top_3()
        foco = self.focar(self.demandas[0], 1, data=date(2026, 10, 20))
        self.assertIsNotNone(foco.pk)

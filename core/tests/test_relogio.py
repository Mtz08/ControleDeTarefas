from datetime import UTC, date, datetime

from django.test import SimpleTestCase

from core import relogio


class HojeNoFusoLocalTests(SimpleTestCase):
    def test_23h30_em_sao_paulo_ainda_e_o_mesmo_dia(self):
        # 23h30 de 19/10 em São Paulo (UTC-3) já é 02h30 de 20/10 em UTC.
        with relogio.congelar(datetime(2026, 10, 20, 2, 30, tzinfo=UTC)):
            self.assertEqual(relogio.hoje(), date(2026, 10, 19))

    def test_00h30_em_sao_paulo_ja_e_o_dia_seguinte(self):
        with relogio.congelar(datetime(2026, 10, 20, 3, 30, tzinfo=UTC)):
            self.assertEqual(relogio.hoje(), date(2026, 10, 20))

    def test_congelar_restaura_o_relogio_ao_sair(self):
        momento = datetime(2020, 1, 1, tzinfo=UTC)
        with relogio.congelar(momento):
            self.assertEqual(relogio.agora(), momento)
        self.assertNotEqual(relogio.agora(), momento)

    def test_congelar_recusa_datetime_sem_fuso(self):
        with self.assertRaises(ValueError), relogio.congelar(datetime(2026, 1, 1)):
            pass

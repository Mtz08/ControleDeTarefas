import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from contas import services
from core import relogio
from core.testes import AGORA_PADRAO, criar_usuario
from demandas import services as demandas_services
from demandas.models import Categoria, Demanda, EventoDemanda, Status
from painel import services as painel_services
from painel.models import FocoDoDia


class DadosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = criar_usuario()

    def setUp(self):
        self.enterContext(relogio.congelar(AGORA_PADRAO))
        self.client.force_login(self.usuario)

    def popular(self):
        categoria = Categoria.objects.create(usuario=self.usuario, nome="Fiscal")
        demanda = demandas_services.criar_demanda(
            self.usuario, titulo='Apurar ICMS; cliente "Alfa"', categoria=categoria
        )
        demandas_services.anotar(demanda, "Pedi o XML")
        painel_services.adicionar_ao_top(self.usuario, demanda)
        demandas_services.criar_demanda(self.usuario, titulo="=SOMA(A1:A2)")
        return demanda


class ExportacaoCsvTests(DadosTestCase):
    def test_csv_para_excel(self):
        self.popular()
        resposta = self.client.get(reverse("contas:exportar_csv"))
        conteudo = resposta.content.decode("utf-8")
        linhas = conteudo.splitlines()
        self.assertTrue(conteudo.startswith("﻿"))
        self.assertIn("ID;Título;Descrição;", linhas[0])
        self.assertIn('"Apurar ICMS; cliente ""Alfa"""', conteudo)  # ";" e aspas escapados
        self.assertIn(";'=SOMA(A1:A2);", conteudo)  # fórmula neutralizada
        self.assertIn("attachment;", resposta["Content-Disposition"])

    def test_csv_so_com_os_meus_dados(self):
        demandas_services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        conteudo = self.client.get(reverse("contas:exportar_csv")).content.decode("utf-8")
        self.assertNotIn("Alheia", conteudo)


class BackupTests(DadosTestCase):
    def test_backup_restaura_tudo_em_banco_vazio(self):
        self.popular()
        resposta = self.client.post(reverse("contas:backup_json"))
        self.assertEqual(resposta["Content-Type"], "application/json")
        antes = self.contagens()

        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "backup.json"
            arquivo.write_bytes(resposta.content)
            get_user_model().objects.all().delete()  # esvazia: cascata leva todo o resto
            self.assertEqual(self.contagens(), (0, 0, 0, 0, 0))
            call_command("loaddata", str(arquivo), verbosity=0)

        self.assertEqual(self.contagens(), antes)
        restaurado = get_user_model().objects.get(username="teste")
        self.assertTrue(restaurado.check_password("senha-ficticia-123"))

    def test_backup_so_por_post_e_sem_dados_alheios(self):
        self.assertEqual(self.client.get(reverse("contas:backup_json")).status_code, 405)
        demandas_services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        dados = json.loads(self.client.post(reverse("contas:backup_json")).content)
        self.assertNotIn("Alheia", json.dumps(dados, ensure_ascii=False))
        usuarios = [o for o in dados if o["model"] == "contas.usuario"]
        self.assertEqual(len(usuarios), 1)

    def contagens(self):
        return (
            get_user_model().objects.count(),
            Categoria.objects.count(),
            Demanda.objects.count(),
            EventoDemanda.objects.count(),
            FocoDoDia.objects.count(),
        )


class ApagarTudoTests(DadosTestCase):
    def test_exige_digitar_excluir(self):
        self.popular()
        resposta = self.client.post(reverse("contas:apagar_tudo"), {"confirmacao": "excluir"})
        self.assertContains(resposta, "Digite exatamente EXCLUIR")
        self.assertEqual(Demanda.objects.count(), 2)

    def test_apaga_dados_e_mantem_usuario_e_dados_alheios(self):
        self.popular()
        alheia = demandas_services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        self.client.post(reverse("contas:apagar_tudo"), {"confirmacao": "EXCLUIR"})
        self.assertEqual(list(Demanda.objects.all()), [alheia])
        self.assertFalse(Categoria.objects.exists())
        self.assertFalse(FocoDoDia.objects.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.usuario.pk).exists())

    def test_retorna_quantas_demandas(self):
        self.popular()
        self.assertEqual(services.apagar_todos_os_dados(self.usuario), 2)


@override_settings(RETENCAO_MESES=12)
class RetencaoTests(DadosTestCase):
    def concluir_em(self, titulo, momento):
        demanda = demandas_services.criar_demanda(self.usuario, titulo=titulo)
        with relogio.congelar(momento):
            return demandas_services.mudar_status(demanda, Status.CONCLUIDA)

    def test_lista_so_fechadas_alem_do_prazo_e_exclui_manualmente(self):
        antiga = self.concluir_em("Antiga", datetime(2025, 10, 1, 12, tzinfo=UTC))
        self.concluir_em("Recente", datetime(2026, 1, 1, 12, tzinfo=UTC))
        demandas_services.criar_demanda(self.usuario, titulo="Aberta")

        tela = self.client.get(reverse("contas:retencao"))
        self.assertContains(tela, "Antiga")
        self.assertNotContains(tela, "Recente")
        self.assertContains(tela, "19/10/2025")

        csv = self.client.get(reverse("contas:retencao_csv")).content.decode("utf-8")
        self.assertIn("Antiga", csv)
        self.assertNotIn("Recente", csv)

        self.assertTrue(Demanda.objects.filter(pk=antiga.pk).exists())  # nada automático
        self.client.post(reverse("contas:retencao_excluir"), {"demanda": [antiga.pk]})
        self.assertFalse(Demanda.objects.filter(pk=antiga.pk).exists())
        self.assertEqual(Demanda.objects.count(), 2)

    def test_nao_exclui_demanda_fora_da_retencao(self):
        recente = self.concluir_em("Recente", datetime(2026, 1, 1, 12, tzinfo=UTC))
        self.client.post(reverse("contas:retencao_excluir"), {"demanda": [recente.pk]})
        self.assertTrue(Demanda.objects.filter(pk=recente.pk).exists())


class PaginasTests(DadosTestCase):
    def test_privacidade_e_meus_dados(self):
        privacidade = self.client.get(reverse("contas:privacidade"))
        self.assertContains(privacidade, "Estados Unidos")
        self.assertContains(privacidade, "12 meses")
        self.assertContains(self.client.get(reverse("contas:meus_dados")), "hash")

    def test_troca_de_senha(self):
        resposta = self.client.post(
            reverse("contas:senha"),
            {
                "old_password": "senha-ficticia-123",
                "new_password1": "outra-senha-bem-longa-42",
                "new_password2": "outra-senha-bem-longa-42",
            },
        )
        self.assertRedirects(resposta, reverse("painel:inicio"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("outra-senha-bem-longa-42"))

    def test_sair_so_por_post(self):
        self.assertEqual(self.client.get(reverse("contas:sair")).status_code, 405)
        self.client.post(reverse("contas:sair"))
        resposta = self.client.get(reverse("painel:inicio"))
        self.assertEqual(resposta.status_code, 302)

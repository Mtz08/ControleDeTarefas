from django.test import TestCase
from django.urls import reverse

from core.testes import criar_usuario
from demandas import services
from demandas.models import Demanda, Status


class ViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = criar_usuario()

    def setUp(self):
        self.client.force_login(self.usuario)


class AcessoTests(TestCase):
    def test_sem_login_redireciona_para_entrar(self):
        for nome in ("painel:inicio", "demandas:lista", "painel:resumo", "contas:meus_dados"):
            resposta = self.client.get(reverse(nome))
            self.assertRedirects(
                resposta, f"{reverse('contas:entrar')}?next={reverse(nome)}", msg_prefix=nome
            )

    def test_tela_de_login_e_robots_sao_publicos(self):
        self.assertEqual(self.client.get(reverse("contas:entrar")).status_code, 200)
        self.assertEqual(self.client.get("/robots.txt").status_code, 200)

    def test_login_com_senha_correta(self):
        criar_usuario("maria")
        resposta = self.client.post(
            reverse("contas:entrar"), {"username": "maria", "password": "senha-ficticia-123"}
        )
        self.assertRedirects(resposta, reverse("painel:inicio"))

    def test_axes_bloqueia_apos_cinco_erros(self):
        criar_usuario("maria")
        for _ in range(5):
            self.client.post(reverse("contas:entrar"), {"username": "maria", "password": "errada"})
        resposta = self.client.post(
            reverse("contas:entrar"), {"username": "maria", "password": "senha-ficticia-123"}
        )
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "temporariamente bloqueado", status_code=429)

    def test_cabecalhos_de_seguranca(self):
        resposta = self.client.get(reverse("contas:entrar"))
        self.assertIn("script-src 'self'", resposta["Content-Security-Policy"])
        self.assertEqual(resposta["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(resposta["X-Frame-Options"], "DENY")


class CapturaTests(ViewTestCase):
    def test_titulo_e_enter_cria_nova_e_volta_para_a_tela(self):
        resposta = self.client.post(
            reverse("demandas:capturar"),
            {"titulo": "Ler circular do sindicato", "origem": "circular", "proximo": "/demandas/"},
        )
        self.assertRedirects(resposta, "/demandas/", fetch_redirect_response=False)
        demanda = Demanda.objects.get()
        self.assertEqual((demanda.status, demanda.origem), (Status.NOVA, "circular"))

    def test_origem_padrao_e_outro(self):
        self.client.post(reverse("demandas:capturar"), {"titulo": "Algo"})
        self.assertEqual(Demanda.objects.get().origem, "outro")

    def test_nao_redireciona_para_outro_site(self):
        resposta = self.client.post(
            reverse("demandas:capturar"), {"titulo": "Algo", "proximo": "https://exemplo.com/"}
        )
        self.assertRedirects(resposta, reverse("painel:inicio"), fetch_redirect_response=False)

    def test_titulo_vazio_nao_cria(self):
        self.client.post(reverse("demandas:capturar"), {"titulo": "   "})
        self.assertFalse(Demanda.objects.exists())

    def test_aviso_de_cpf_sem_bloquear(self):
        resposta = self.client.post(
            reverse("demandas:capturar"), {"titulo": "Cliente 529.982.247-25"}, follow=True
        )
        self.assertContains(resposta, "parece haver um CPF")
        self.assertTrue(Demanda.objects.exists())

    def test_captura_aparece_em_todas_as_telas(self):
        for nome in ("painel:inicio", "demandas:lista", "painel:resumo", "contas:meus_dados"):
            self.assertContains(
                self.client.get(reverse(nome)), 'id="captura-titulo"', msg_prefix=nome
            )


class IsolamentoTests(ViewTestCase):
    def test_demanda_de_outro_usuario_da_404(self):
        alheia = services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        for nome in ("demandas:detalhe", "demandas:editar", "demandas:excluir"):
            self.assertEqual(self.client.get(reverse(nome, args=[alheia.pk])).status_code, 404)
        resposta = self.client.post(reverse("demandas:acao", args=[alheia.pk, "concluir"]))
        self.assertEqual(resposta.status_code, 404)
        alheia.refresh_from_db()
        self.assertEqual(alheia.status, Status.NOVA)

    def test_lista_mostra_so_as_minhas(self):
        services.criar_demanda(criar_usuario("outro"), titulo="Alheia")
        services.criar_demanda(self.usuario, titulo="Minha")
        resposta = self.client.get(reverse("demandas:lista"))
        self.assertContains(resposta, "Minha")
        self.assertNotContains(resposta, "Alheia")


class ListaTests(ViewTestCase):
    def test_busca_por_texto_e_filtro_de_status(self):
        services.criar_demanda(self.usuario, titulo="Folha de outubro", solicitante="RH")
        concluida = services.criar_demanda(self.usuario, titulo="Folha de setembro")
        services.mudar_status(concluida, Status.CONCLUIDA)

        resposta = self.client.get(reverse("demandas:lista"), {"q": "folha"})
        self.assertContains(resposta, "Folha de outubro")
        self.assertNotContains(resposta, "Folha de setembro")  # padrão: só abertas

        resposta = self.client.get(reverse("demandas:lista"), {"q": "folha", "status": "todas"})
        self.assertContains(resposta, "Folha de setembro")

        resposta = self.client.get(reverse("demandas:lista"), {"q": "rh"})
        self.assertContains(resposta, "Folha de outubro")

    def test_paginacao(self):
        for n in range(30):
            services.criar_demanda(self.usuario, titulo=f"Demanda {n}")
        resposta = self.client.get(reverse("demandas:lista"), {"pagina": 2})
        self.assertContains(resposta, "Página 2 de 2")


class EdicaoTests(ViewTestCase):
    def dados_do_form(self, demanda, **mudancas):
        dados = {
            "titulo": demanda.titulo,
            "origem": demanda.origem,
            "prioridade": demanda.prioridade,
            "recebida_em": "2026-10-19T09:00",
            "status": demanda.status,
            "versao": demanda.versao,
        }
        dados.update(mudancas)
        return dados

    def test_triagem_pelo_formulario(self):
        demanda = services.criar_demanda(self.usuario, titulo="Triar isto")
        url = reverse("demandas:editar", args=[demanda.pk])
        self.assertContains(self.client.get(url), "Triar demanda")
        resposta = self.client.post(
            url, self.dados_do_form(demanda, status="a_fazer", prioridade="alta")
        )
        self.assertRedirects(resposta, reverse("demandas:detalhe", args=[demanda.pk]))
        demanda.refresh_from_db()
        self.assertEqual((demanda.status, demanda.prioridade), ("a_fazer", "alta"))

    def test_nova_nao_aparece_como_opcao_depois_da_triagem(self):
        demanda = services.criar_demanda(self.usuario, titulo="X", status=Status.A_FAZER)
        resposta = self.client.get(reverse("demandas:editar", args=[demanda.pk]))
        self.assertNotContains(resposta, 'value="nova"')

    def test_edicao_em_duas_abas_avisa_e_nao_sobrescreve(self):
        demanda = services.criar_demanda(self.usuario, titulo="Original")
        url = reverse("demandas:editar", args=[demanda.pk])
        self.client.post(url, self.dados_do_form(demanda, titulo="Aba A"))
        resposta = self.client.post(url, self.dados_do_form(demanda, titulo="Aba B"), follow=True)
        self.assertContains(resposta, "alterada em outra aba")
        demanda.refresh_from_db()
        self.assertEqual(demanda.titulo, "Aba A")

    def test_aguardando_exige_de_quem_no_formulario(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        resposta = self.client.post(
            reverse("demandas:editar", args=[demanda.pk]),
            self.dados_do_form(demanda, status="aguardando"),
        )
        self.assertContains(resposta, "Informe de quem")

    def test_recebida_no_futuro_e_recusada(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        resposta = self.client.post(
            reverse("demandas:editar", args=[demanda.pk]),
            self.dados_do_form(demanda, recebida_em="2099-01-01T10:00"),
        )
        self.assertContains(resposta, "não pode estar no futuro")


class AcoesTests(ViewTestCase):
    def test_acoes_rapidas_mudam_status(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        self.client.post(reverse("demandas:acao", args=[demanda.pk, "iniciar"]))
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, Status.EM_ANDAMENTO)
        self.client.post(reverse("demandas:acao", args=[demanda.pk, "concluir"]))
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, Status.CONCLUIDA)

    def test_acao_so_por_post(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        resposta = self.client.get(reverse("demandas:acao", args=[demanda.pk, "concluir"]))
        self.assertEqual(resposta.status_code, 405)

    def test_aguardar_pede_de_quem(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        url = reverse("demandas:aguardar", args=[demanda.pk])
        self.client.post(url, {"aguardando_quem": "Banco", "versao": demanda.versao})
        demanda.refresh_from_db()
        self.assertEqual((demanda.status, demanda.aguardando_quem), ("aguardando", "Banco"))

    def test_anotar_e_excluir_com_confirmacao(self):
        demanda = services.criar_demanda(self.usuario, titulo="X")
        self.client.post(reverse("demandas:anotar", args=[demanda.pk]), {"texto": "Liguei"})
        detalhe = self.client.get(reverse("demandas:detalhe", args=[demanda.pk]))
        self.assertContains(detalhe, "Liguei")

        url = reverse("demandas:excluir", args=[demanda.pk])
        self.assertContains(self.client.get(url), "Excluir demanda?")
        self.client.post(url)
        self.assertFalse(Demanda.objects.exists())

    def test_cadastro_completo(self):
        resposta = self.client.post(
            reverse("demandas:nova"),
            {
                "titulo": "Fechamento",
                "origem": "email",
                "prioridade": "alta",
                "recebida_em": "2026-10-01T08:00",
                "prazo": "2026-10-30",
                "status": "a_fazer",
            },
        )
        demanda = Demanda.objects.get()
        self.assertRedirects(resposta, reverse("demandas:detalhe", args=[demanda.pk]))
        self.assertEqual(demanda.status, Status.A_FAZER)

    def test_texto_digitado_e_escapado(self):
        services.criar_demanda(self.usuario, titulo="<script>alert(1)</script>")
        resposta = self.client.get(reverse("demandas:lista"))
        self.assertNotContains(resposta, "<script>alert(1)</script>")
        self.assertContains(resposta, "&lt;script&gt;")

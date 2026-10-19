from datetime import date, timedelta
from unittest import mock

from django.test import TestCase

from core import relogio
from core.testes import AGORA_PADRAO, criar_usuario
from demandas import services
from demandas.models import Categoria, Demanda, EventoDemanda, Prioridade, Status, TipoEvento


class ServicoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = criar_usuario()

    def setUp(self):
        self.enterContext(relogio.congelar(AGORA_PADRAO))

    def criar(self, **campos):
        campos.setdefault("titulo", "Conferir guia DAS")
        return services.criar_demanda(self.usuario, **campos)

    def tipos_de_evento(self, demanda):
        return list(demanda.eventos.values_list("tipo", flat=True))


class CriarDemandaTests(ServicoTestCase):
    def test_cria_nova_com_evento_criada(self):
        demanda = self.criar(titulo="  Responder circular  ")
        self.assertEqual(demanda.titulo, "Responder circular")
        self.assertEqual(demanda.status, Status.NOVA)
        self.assertEqual(demanda.recebida_em, AGORA_PADRAO)
        self.assertEqual(self.tipos_de_evento(demanda), [TipoEvento.CRIADA])

    def test_atomicidade_erro_no_evento_desfaz_a_demanda(self):
        with (
            mock.patch.object(services, "_registrar", side_effect=RuntimeError("falha simulada")),
            self.assertRaises(RuntimeError),
        ):
            self.criar()
        self.assertFalse(Demanda.objects.exists())

    def test_categoria_de_outro_usuario_e_recusada(self):
        alheia = Categoria.objects.create(usuario=criar_usuario("outro"), nome="Fiscal")
        with self.assertRaises(services.DadosInvalidos):
            self.criar(categoria=alheia)

    def test_criar_aguardando_exige_quem(self):
        with self.assertRaises(services.DadosInvalidos):
            self.criar(status=Status.AGUARDANDO)
        demanda = self.criar(status=Status.AGUARDANDO, aguardando_quem="Contador do cliente")
        self.assertEqual(demanda.aguardando_quem, "Contador do cliente")

    def test_nao_cria_fechada(self):
        with self.assertRaises(services.DadosInvalidos):
            self.criar(status=Status.CONCLUIDA)


class MudarStatusTests(ServicoTestCase):
    def test_concluir_preenche_e_reabrir_limpa_concluida_em(self):
        demanda = services.mudar_status(self.criar(), Status.CONCLUIDA)
        self.assertEqual(demanda.concluida_em, AGORA_PADRAO)
        self.assertEqual(demanda.status_alterado_em, AGORA_PADRAO)

        demanda = services.mudar_status(demanda, Status.A_FAZER)
        self.assertIsNone(demanda.concluida_em)
        self.assertEqual(demanda.status, Status.A_FAZER)

    def test_transicao_proibida(self):
        demanda = services.mudar_status(self.criar(), Status.CANCELADA)
        with self.assertRaises(services.TransicaoInvalida):
            services.mudar_status(demanda, Status.EM_ANDAMENTO)
        demanda = services.mudar_status(demanda, Status.A_FAZER)
        with self.assertRaises(services.TransicaoInvalida):
            services.mudar_status(demanda, Status.NOVA)

    def test_aguardar_e_sair_de_aguardando(self):
        demanda = services.mudar_status(
            self.criar(), Status.AGUARDANDO, aguardando_quem="Retorno da Receita"
        )
        self.assertEqual(demanda.aguardando_quem, "Retorno da Receita")

        demanda = services.mudar_status(demanda, Status.EM_ANDAMENTO)
        self.assertEqual(demanda.aguardando_quem, "")
        ultimo = demanda.eventos.last()
        self.assertEqual(ultimo.texto, "Aguardava: Retorno da Receita")

    def test_cada_mudanca_registra_evento_e_incrementa_versao(self):
        demanda = self.criar()
        demanda = services.mudar_status(demanda, Status.EM_ANDAMENTO)
        self.assertEqual(demanda.versao, 2)
        evento = demanda.eventos.get(tipo=TipoEvento.STATUS)
        self.assertEqual((evento.valor_anterior, evento.valor_novo), ("nova", "em_andamento"))

    def test_versao_desatualizada_gera_conflito(self):
        demanda = self.criar()
        services.mudar_status(demanda, Status.EM_ANDAMENTO, versao=1)
        with self.assertRaises(services.ConflitoDeEdicao):
            services.mudar_status(demanda, Status.CONCLUIDA, versao=1)


class EditarDemandaTests(ServicoTestCase):
    def dados(self, demanda, **mudancas):
        campos = {
            "titulo": demanda.titulo,
            "descricao": demanda.descricao,
            "solicitante": demanda.solicitante,
            "referencia": demanda.referencia,
            "origem": demanda.origem,
            "categoria": demanda.categoria,
            "prioridade": demanda.prioridade,
            "prazo": demanda.prazo,
            "recebida_em": demanda.recebida_em,
        }
        campos.update(mudancas)
        return campos

    def test_triagem_registra_prioridade_prazo_status_e_edicao(self):
        demanda = self.criar()
        prazo = date(2026, 10, 25)
        demanda = services.editar_demanda(
            demanda,
            versao=demanda.versao,
            dados=self.dados(
                demanda, prioridade=Prioridade.ALTA, prazo=prazo, solicitante="Fiscal"
            ),
            status=Status.A_FAZER,
        )
        self.assertEqual(demanda.status, Status.A_FAZER)
        self.assertEqual(demanda.versao, 2)
        self.assertEqual(
            self.tipos_de_evento(demanda),
            [
                TipoEvento.CRIADA,
                TipoEvento.PRIORIDADE,
                TipoEvento.PRAZO,
                TipoEvento.STATUS,
                TipoEvento.EDICAO,
            ],
        )
        self.assertEqual(demanda.eventos.get(tipo=TipoEvento.PRAZO).valor_novo, "2026-10-25")

    def test_sem_mudanca_nao_gera_evento_nem_versao(self):
        demanda = self.criar()
        demanda = services.editar_demanda(
            demanda, versao=1, dados=self.dados(demanda), status=Status.NOVA
        )
        self.assertEqual(demanda.versao, 1)
        self.assertEqual(demanda.eventos.count(), 1)

    def test_conflito_de_edicao_nao_sobrescreve(self):
        demanda = self.criar()
        services.editar_demanda(demanda, versao=1, dados=self.dados(demanda, titulo="Aba A"))
        with self.assertRaises(services.ConflitoDeEdicao):
            services.editar_demanda(demanda, versao=1, dados=self.dados(demanda, titulo="Aba B"))
        demanda.refresh_from_db()
        self.assertEqual(demanda.titulo, "Aba A")

    def test_erro_no_meio_da_edicao_desfaz_tudo(self):
        demanda = self.criar()
        with self.assertRaises(services.DadosInvalidos):
            services.editar_demanda(
                demanda,
                versao=1,
                dados=self.dados(demanda, prioridade=Prioridade.ALTA),
                # Sem "aguardando quem": falha depois de gravar o evento de prioridade.
                status=Status.AGUARDANDO,
            )
        demanda.refresh_from_db()
        self.assertEqual(demanda.prioridade, Prioridade.MEDIA)
        self.assertEqual(demanda.eventos.count(), 1)


class AnotarExcluirTests(ServicoTestCase):
    def test_anotacao_vazia_e_recusada(self):
        with self.assertRaises(services.DadosInvalidos):
            services.anotar(self.criar(), "   ")

    def test_excluir_leva_o_historico(self):
        demanda = self.criar()
        services.anotar(demanda, "Pedi documentos ao cliente")
        services.excluir_demanda(demanda)
        self.assertFalse(Demanda.objects.exists())
        self.assertFalse(EventoDemanda.objects.exists())


class RecebidaNoPassadoTests(ServicoTestCase):
    def test_recebida_em_pode_ser_anterior(self):
        ontem = AGORA_PADRAO - timedelta(days=1)
        self.assertEqual(self.criar(recebida_em=ontem).recebida_em, ontem)

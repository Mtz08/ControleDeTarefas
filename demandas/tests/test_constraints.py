"""As regras críticas valem no banco, mesmo gravando por fora dos formulários."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from core import relogio
from demandas.models import Categoria, Demanda, EventoDemanda, Status, TipoEvento


class ConstraintTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("teste", password="senha-ficticia-123")

    def nova_demanda(self, **campos):
        campos.setdefault("titulo", "Conferir guia")
        return Demanda.objects.create(usuario=self.usuario, **campos)

    def assertRejeitadoPeloBanco(self, criar):
        # Cada violação roda em um savepoint próprio para não invalidar o resto do teste.
        with self.assertRaises(IntegrityError), transaction.atomic():
            criar()


class DemandaConstraintsTests(ConstraintTestCase):
    def test_demanda_valida_usa_os_padroes(self):
        demanda = self.nova_demanda()
        self.assertEqual(demanda.status, Status.NOVA)
        self.assertEqual(demanda.prioridade, "media")
        self.assertEqual(demanda.origem, "outro")
        self.assertEqual(demanda.versao, 1)

    def test_titulo_vazio_ou_so_com_espacos(self):
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(titulo=""))
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(titulo="   "))

    def test_valores_fora_das_opcoes(self):
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(origem="fax"))
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(prioridade="urgente"))
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(status="arquivada"))


class ConcluidaConstraintTests(ConstraintTestCase):
    def test_concluida_exige_concluida_em(self):
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(status=Status.CONCLUIDA))

    def test_concluida_em_so_vale_para_concluida(self):
        self.assertRejeitadoPeloBanco(
            lambda: self.nova_demanda(status=Status.A_FAZER, concluida_em=relogio.agora())
        )

    def test_concluida_com_data_e_aceita(self):
        demanda = self.nova_demanda(status=Status.CONCLUIDA, concluida_em=relogio.agora())
        self.assertIsNotNone(demanda.pk)


class AguardandoConstraintTests(ConstraintTestCase):
    def test_aguardando_exige_de_quem(self):
        self.assertRejeitadoPeloBanco(lambda: self.nova_demanda(status=Status.AGUARDANDO))
        self.assertRejeitadoPeloBanco(
            lambda: self.nova_demanda(status=Status.AGUARDANDO, aguardando_quem="  ")
        )

    def test_aguardando_quem_so_vale_no_status_aguardando(self):
        self.assertRejeitadoPeloBanco(
            lambda: self.nova_demanda(status=Status.A_FAZER, aguardando_quem="Cliente X")
        )

    def test_aguardando_com_de_quem_e_aceito(self):
        demanda = self.nova_demanda(status=Status.AGUARDANDO, aguardando_quem="Cliente X")
        self.assertIsNotNone(demanda.pk)


class CategoriaConstraintsTests(ConstraintTestCase):
    def test_nome_unico_por_usuario_sem_diferenciar_maiusculas(self):
        Categoria.objects.create(usuario=self.usuario, nome="Fiscal")
        self.assertRejeitadoPeloBanco(
            lambda: Categoria.objects.create(usuario=self.usuario, nome="fiscal")
        )

    def test_mesmo_nome_para_outro_usuario_e_aceito(self):
        outro = get_user_model().objects.create_user("outro", password="senha-ficticia-123")
        Categoria.objects.create(usuario=self.usuario, nome="Fiscal")
        self.assertIsNotNone(Categoria.objects.create(usuario=outro, nome="Fiscal").pk)

    def test_nome_vazio(self):
        self.assertRejeitadoPeloBanco(
            lambda: Categoria.objects.create(usuario=self.usuario, nome=" ")
        )

    def test_excluir_categoria_mantem_a_demanda(self):
        categoria = Categoria.objects.create(usuario=self.usuario, nome="Fiscal")
        demanda = self.nova_demanda(categoria=categoria)
        categoria.delete()
        demanda.refresh_from_db()
        self.assertIsNone(demanda.categoria)


class EventoConstraintsTests(ConstraintTestCase):
    def test_tipo_invalido(self):
        demanda = self.nova_demanda()
        self.assertRejeitadoPeloBanco(
            lambda: EventoDemanda.objects.create(demanda=demanda, tipo="outro")
        )

    def test_nota_exige_texto(self):
        demanda = self.nova_demanda()
        self.assertRejeitadoPeloBanco(
            lambda: EventoDemanda.objects.create(demanda=demanda, tipo=TipoEvento.NOTA)
        )

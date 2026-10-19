import logging
from datetime import date

from django.db import IntegrityError, OperationalError
from django.test import RequestFactory, SimpleTestCase, override_settings

from core import relogio
from core.logs import SemDadosDoBancoFilter
from core.rede import ip_do_cliente
from core.views import erro_500


class IpDoClienteTests(SimpleTestCase):
    def requisicao(self, encaminhado=None):
        extras = {"REMOTE_ADDR": "10.0.0.1"}
        if encaminhado is not None:
            extras["HTTP_X_FORWARDED_FOR"] = encaminhado
        return RequestFactory().get("/", **extras)

    @override_settings(PROXIES_CONFIAVEIS=0)
    def test_sem_proxy_usa_remote_addr_e_ignora_cabecalho(self):
        self.assertEqual(ip_do_cliente(self.requisicao("1.2.3.4")), "10.0.0.1")

    @override_settings(PROXIES_CONFIAVEIS=1)
    def test_com_proxy_usa_o_ip_gravado_pelo_proxy(self):
        self.assertEqual(ip_do_cliente(self.requisicao("203.0.113.9")), "203.0.113.9")

    @override_settings(PROXIES_CONFIAVEIS=1)
    def test_valor_forjado_a_esquerda_e_ignorado(self):
        self.assertEqual(ip_do_cliente(self.requisicao("6.6.6.6, 203.0.113.9")), "203.0.113.9")

    @override_settings(PROXIES_CONFIAVEIS=1)
    def test_cabecalho_ausente_ou_invalido(self):
        self.assertEqual(ip_do_cliente(self.requisicao()), "10.0.0.1")
        self.assertEqual(ip_do_cliente(self.requisicao("nao-e-ip")), "10.0.0.1")


class LogsTests(SimpleTestCase):
    def test_erro_de_banco_perde_os_detalhes(self):
        try:
            raise IntegrityError('Failing row contains (1, "Cliente Alfa", ...)')
        except IntegrityError as erro:
            registro = logging.LogRecord(
                "django.request",
                logging.ERROR,
                "",
                0,
                "Erro em %s",
                ("/x",),
                (type(erro), erro, None),
            )
        SemDadosDoBancoFilter().filter(registro)
        self.assertIsNone(registro.exc_info)
        self.assertEqual(registro.getMessage(), "Erro em /x [IntegrityError, detalhes omitidos]")


class Erro500Tests(SimpleTestCase):
    def test_banco_indisponivel_vira_503_amigavel(self):
        try:
            raise OperationalError("connection timeout expired")
        except OperationalError:
            resposta = erro_500(RequestFactory().get("/"))
        self.assertEqual(resposta.status_code, 503)
        self.assertIn("acordando", resposta.content.decode())

    def test_outro_erro_vira_500_sem_detalhes(self):
        try:
            raise ValueError("segredo interno")
        except ValueError:
            resposta = erro_500(RequestFactory().get("/"))
        self.assertEqual(resposta.status_code, 500)
        self.assertNotIn("segredo", resposta.content.decode())


class SubtrairMesesTests(SimpleTestCase):
    def test_casos(self):
        self.assertEqual(relogio.subtrair_meses(date(2026, 10, 19), 12), date(2025, 10, 19))
        self.assertEqual(relogio.subtrair_meses(date(2026, 3, 31), 1), date(2026, 2, 28))
        self.assertEqual(relogio.subtrair_meses(date(2026, 1, 15), 1), date(2025, 12, 15))

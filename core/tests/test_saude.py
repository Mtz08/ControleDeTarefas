from django.test import SimpleTestCase


class SaudeTests(SimpleTestCase):
    # SimpleTestCase proíbe acesso ao banco: se /saude consultasse o banco, o teste falharia.

    def test_responde_200_sem_banco(self):
        resposta = self.client.get("/saude")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"ok")

    def test_responde_mesmo_com_host_desconhecido(self):
        resposta = self.client.get("/saude", HTTP_HOST="host-desconhecido.example")
        self.assertEqual(resposta.status_code, 200)

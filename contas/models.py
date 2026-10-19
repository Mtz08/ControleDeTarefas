from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Usuário do sistema.

    Sem campos extras na v1, mas customizado desde o início: trocar o modelo de
    usuário depois que o banco já tem dados é uma migração difícil.
    """

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.get_username()

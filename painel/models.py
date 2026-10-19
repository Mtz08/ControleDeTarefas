from django.conf import settings
from django.db import models
from django.db.models import Q

from demandas.models import Demanda

LIMITE_TOP = 3


class FocoDoDia(models.Model):
    """Uma posição do Top 3 de um dia.

    O limite de 3 itens é garantido pelo banco: `ordem` só aceita 1 a 3 e cada
    ordem é única no dia. Um 4º item não tem onde entrar, sem precisar "contar
    antes de inserir".
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="focos",
        # O índice do UNIQUE (usuario, data, ordem) já começa por usuario.
        db_index=False,
    )
    data = models.DateField()
    ordem = models.PositiveSmallIntegerField()
    demanda = models.ForeignKey(Demanda, on_delete=models.CASCADE, related_name="focos")

    class Meta:
        ordering = ["data", "ordem"]
        verbose_name = "foco do dia"
        verbose_name_plural = "focos do dia"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "data", "ordem"], name="foco_ordem_unica_no_dia"
            ),
            models.UniqueConstraint(
                fields=["usuario", "data", "demanda"], name="foco_demanda_unica_no_dia"
            ),
            models.CheckConstraint(
                condition=Q(ordem__gte=1, ordem__lte=LIMITE_TOP), name="foco_ordem_entre_1_e_3"
            ),
        ]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} #{self.ordem}"

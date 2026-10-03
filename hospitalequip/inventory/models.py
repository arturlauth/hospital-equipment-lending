from django.db import models


class Warehouse(models.Model):
    name = models.CharField("nome", max_length=100, unique=True)
    address = models.CharField("endereço", max_length=200, blank=True)

    class Meta:
        verbose_name = "depósito"
        verbose_name_plural = "depósitos"

    def __str__(self):
        return self.name


class Equipment(models.Model):
    name = models.CharField("nome", max_length=100)
    category = models.CharField("categoria", max_length=50)
    description = models.TextField("descrição", blank=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="equipment",
        verbose_name="depósito",
    )
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)

    class Meta:
        verbose_name = "equipamento"
        verbose_name_plural = "equipamentos"

    def __str__(self):
        return f"{self.name} ({self.category})"

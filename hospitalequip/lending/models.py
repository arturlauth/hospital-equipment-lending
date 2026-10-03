from django.db import models
from django.db.models import F, Q


class Person(models.Model):
    name = models.CharField("nome", max_length=150)
    cpf = models.CharField("CPF", max_length=11, unique=True, help_text="Somente números.")
    birth_date = models.DateField("data de nascimento")
    phone = models.CharField("telefone", max_length=30)
    email = models.EmailField("e-mail", blank=True)

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"

    def __str__(self):
        return self.name


class Loan(models.Model):
    equipment = models.ForeignKey(
        "inventory.Equipment",
        on_delete=models.PROTECT,
        related_name="loans",
        verbose_name="equipamento",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="loans",
        verbose_name="pessoa",
    )
    lent_date = models.DateField("emprestado em")
    due_date = models.DateField("devolução prevista", null=True, blank=True)
    return_date = models.DateField("devolvido em", null=True, blank=True)

    class Meta:
        verbose_name = "empréstimo"
        verbose_name_plural = "empréstimos"
        constraints = [
            models.CheckConstraint(
                condition=Q(due_date__isnull=True) | Q(due_date__gte=F("lent_date")),
                name="loan_due_not_before_lent",
            ),
            models.CheckConstraint(
                condition=Q(return_date__isnull=True) | Q(return_date__gte=F("lent_date")),
                name="loan_return_not_before_lent",
            ),
            models.UniqueConstraint(
                fields=["equipment"],
                condition=Q(return_date__isnull=True),
                name="loan_one_open_per_equipment",
            ),
        ]

    def __str__(self):
        return f"{self.equipment} → {self.person}"
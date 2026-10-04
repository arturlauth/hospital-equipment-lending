from django.db import models
from django.db.models import F, Q

from .validators import only_digits, validate_cep, validate_cpf

LOAN_TERM_MONTHS = 6  # suggested time until the due date; staff can change it per loan

STATES = [
    (uf, uf)
    for uf in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
]


class Person(models.Model):
    """A borrower or guarantor. Registered by staff; never logs in."""

    name = models.CharField("nome", max_length=150)
    cpf = models.CharField("CPF", max_length=11, unique=True, validators=[validate_cpf])
    rg = models.CharField("RG", max_length=20, blank=True)
    birth_date = models.DateField("data de nascimento")
    phone = models.CharField("telefone", max_length=30)
    email = models.EmailField("e-mail", blank=True)
    street = models.CharField("rua", max_length=150)
    number = models.CharField("número", max_length=20)
    complement = models.CharField("complemento", max_length=60, blank=True)
    neighborhood = models.CharField("bairro", max_length=80)
    city = models.CharField("cidade", max_length=80)
    state = models.CharField("UF", max_length=2, choices=STATES)
    cep = models.CharField("CEP", max_length=8, validators=[validate_cep])

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.cpf = only_digits(self.cpf)
        self.cep = only_digits(self.cep)
        super().save(*args, **kwargs)

    @property
    def cpf_display(self):
        c = self.cpf
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c


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
        verbose_name="beneficiário",
    )
    # The "solidário" (UI name). Nullable only for loans recorded before guarantors existed; the lend form requires one.
    guarantor = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="guaranteed_loans",
        verbose_name="solidário",
        null=True,
        blank=True,
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
            models.CheckConstraint(
                condition=~Q(guarantor=F("person")),
                name="loan_guarantor_is_not_borrower",
            ),
            models.UniqueConstraint(
                fields=["equipment"],
                condition=Q(return_date__isnull=True),
                name="loan_one_open_per_equipment",
            ),
        ]

    def __str__(self):
        return f"{self.equipment} → {self.person}"

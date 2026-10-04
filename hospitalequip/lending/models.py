from datetime import date

from django.conf import settings
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

    @property
    def is_overdue(self):
        """Still open and past its due date; due today is not late yet."""
        return (
            self.return_date is None and self.due_date is not None and self.due_date < date.today()
        )


FIELD_LABELS = {
    "lent_date": "Emprestado em",
    "due_date": "Devolução prevista",
    "return_date": "Devolvido em",
}


class LoanLog(models.Model):
    """One action on a loan: who did it, when, and the fields it changed as {field: [old, new]}.

    Dates in `changes` are ISO strings. Written in the same transaction as the change.
    """

    class Action(models.TextChoices):
        LENT = "lent", "Emprestado"
        RETURNED = "returned", "Devolvido"
        EDITED = "edited", "Editado"
        REOPENED = "reopened", "Devolução desfeita"

    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, related_name="logs", verbose_name="empréstimo"
    )
    action = models.CharField("ação", max_length=20, choices=Action.choices)
    changes = models.JSONField("alterações", default=dict, blank=True)
    reason = models.TextField("motivo", blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="por"
    )
    created_at = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "registro do empréstimo"
        verbose_name_plural = "registros do empréstimo"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.loan}: {self.get_action_display()}"

    @classmethod
    def record(cls, loan, action, by, old=None, reason=""):
        """Log `action`; `old` maps field -> value before the change, unchanged ones are dropped."""
        changes = {}
        for field, before in (old or {}).items():
            after = getattr(loan, field)
            if before != after:
                changes[field] = [_iso(before), _iso(after)]
        return cls.objects.create(
            loan=loan, action=action, changes=changes, reason=reason, changed_by=by
        )

    def change_rows(self):
        """(label, old, new) per changed field, for display; an unknown field shows its key."""
        return [
            (FIELD_LABELS.get(field, field), _from_iso(old), _from_iso(new))
            for field, (old, new) in self.changes.items()
        ]


def _iso(value):
    return value.isoformat() if isinstance(value, date) else value


def _from_iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return value

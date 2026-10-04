from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Max, Q

MIN_PUBLIC_IMAGES = 3
OPEN_LOAN = Q(loans__return_date__isnull=True)


class Warehouse(models.Model):
    name = models.CharField("nome", max_length=100, unique=True)
    address = models.CharField("endereço", max_length=200, blank=True)

    class Meta:
        verbose_name = "depósito"
        verbose_name_plural = "depósitos"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("nome", max_length=50, unique=True)
    code = models.CharField(
        "código",
        max_length=20,
        unique=True,
        help_text="Prefixo do patrimônio, ex.: ANDADOR. Não altere depois de cadastrar itens.",
    )

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class EquipmentQuerySet(models.QuerySet):
    def with_availability(self):
        """Annotate `open_loans` and `lent_until` (due date of the open loan), read from lending.

        Lent is derived from an open loan, never stored on Equipment.
        """
        return self.annotate(
            open_loans=Count("loans", filter=OPEN_LOAN, distinct=True),
            lent_until=Max("loans__due_date", filter=OPEN_LOAN),
        )

    def public(self):
        """Items shown to the public: not lost or written off, with at least MIN_PUBLIC_IMAGES photos."""
        return (
            self.exclude(status__in=[Equipment.Status.LOST, Equipment.Status.WRITTEN_OFF])
            .annotate(image_count=Count("images", distinct=True))
            .filter(image_count__gte=MIN_PUBLIC_IMAGES)
            .with_availability()
        )


class Equipment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        DAMAGED = "damaged", "Em manutenção"
        LOST = "lost", "Extraviado"
        WRITTEN_OFF = "written_off", "Baixado"

    name = models.CharField("nome", max_length=100)
    brand = models.CharField("marca", max_length=100, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="equipment",
        verbose_name="categoria",
    )
    sequence = models.PositiveIntegerField("número", editable=False)
    tag = models.CharField("patrimônio", max_length=30, unique=True, editable=False)
    description = models.TextField("descrição", blank=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="equipment",
        verbose_name="depósito",
    )
    status = models.CharField(
        "situação", max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    value = models.DecimalField(
        "valor (R$)", max_digits=10, decimal_places=2, null=True, blank=True
    )
    acquired_on = models.DateField("data de aquisição", null=True, blank=True)
    created_at = models.DateTimeField("cadastrado em", auto_now_add=True)

    objects = EquipmentQuerySet.as_manager()

    class Meta:
        verbose_name = "equipamento"
        verbose_name_plural = "equipamentos"
        constraints = [
            models.CheckConstraint(
                condition=Q(value__isnull=True) | Q(value__gte=0),
                name="equipment_value_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.tag} - {self.name}"

    def save(self, *args, **kwargs):
        """On creation, assign the asset tag: category code + next number in that category.

        Pass `sequence` explicitly to import an item that already has a physical plate; later
        items continue after the highest number in the category. The tag never changes after.
        """
        if self._state.adding and not self.tag:
            with transaction.atomic():
                # Lock the category row so two simultaneous creations cannot take the same number.
                category = Category.objects.select_for_update().get(pk=self.category_id)
                if self.sequence is None:
                    last = category.equipment.aggregate(last=Max("sequence"))["last"] or 0
                    self.sequence = last + 1
                self.tag = f"{category.code} {self.sequence:04d}"
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        """Lendable right now. Needs a queryset built with `with_availability()`."""
        return self.status == self.Status.ACTIVE and self.open_loans == 0


class EquipmentStatusLog(models.Model):
    """One status change, written only by `services.change_status`. Newest first."""

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name="status_logs",
        verbose_name="equipamento",
    )
    from_status = models.CharField("de", max_length=20, choices=Equipment.Status.choices)
    to_status = models.CharField("para", max_length=20, choices=Equipment.Status.choices)
    effective_on = models.DateField("em")
    reason = models.TextField("motivo")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="por"
    )
    created_at = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "mudança de situação"
        verbose_name_plural = "mudanças de situação"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_status=models.F("to_status")),
                name="status_log_changes_status",
            ),
        ]

    def __str__(self):
        return f"{self.equipment}: {self.from_status} → {self.to_status}"


class EquipmentImage(models.Model):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name="images", verbose_name="equipamento"
    )
    image = models.ImageField("imagem", upload_to="equipment/")
    order = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "imagem"
        verbose_name_plural = "imagens"
        ordering = ["order", "id"]

    def __str__(self):
        return self.image.name


class EquipmentSpec(models.Model):
    """One row of the specification table, e.g. Dimensões / Capacidade máxima / 120 kg."""

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name="specs", verbose_name="equipamento"
    )
    section = models.CharField("seção", max_length=60)
    label = models.CharField("item", max_length=100)
    value = models.CharField("valor", max_length=200)
    order = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "especificação"
        verbose_name_plural = "especificações"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.label}: {self.value}"

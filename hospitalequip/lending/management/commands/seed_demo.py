"""Fill an empty database with demo data that exercises every screen.

Dates are relative to today, so late loans stay late whenever the command runs. Inventory rows
are built through `apps.get_model` and status changes through `inventory.services`, so the
app boundary (Import Linter) holds.
"""

import random
from datetime import date, timedelta
from pathlib import Path

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hospitalequip.inventory.services import change_status
from hospitalequip.staff import roles

from ...models import Loan, LoanLog, Person
from ...validators import cpf_check_digits

WAREHOUSES = [
    ("Depósito Centro", "Rua Barão de Piumhi, 200, Centro, Formiga - MG"),
    ("Depósito Água Vermelha", "Rua das Acácias, 45, Água Vermelha, Formiga - MG"),
]

# (category, code, [(name, brand, value)], specs as (section, label, value))
CATALOG = [
    (
        "Andador",
        "ANDADOR",
        [
            ("Andador articulado", "Mobil", 289),
            ("Andador fixo dobrável", "Ortobras", 219),
            ("Andador com rodas", "Dellamed", 349),
            ("Andador infantil", "Mobil", 310),
            ("Andador de alumínio", "Ortobras", 199),
        ],
        [
            ("Medidas", "Altura regulável", "78 a 95 cm"),
            ("Medidas", "Peso", "2,4 kg"),
            ("Uso", "Capacidade máxima", "100 kg"),
        ],
    ),
    (
        "Cadeira de rodas",
        "CADEIRA",
        [
            ("Cadeira de rodas adulto", "Jaguaribe", 890),
            ("Cadeira de rodas dobrável", "Ortobras", 760),
            ("Cadeira de rodas obeso", "Jaguaribe", 1890),
            ("Cadeira de rodas infantil", "Ortobras", 980),
            ("Cadeira de rodas leve", "Freedom", 1450),
            ("Cadeira de rodas reclinável", "Jaguaribe", 2100),
        ],
        [
            ("Medidas", "Largura do assento", "44 cm"),
            ("Medidas", "Peso", "16 kg"),
            ("Uso", "Capacidade máxima", "120 kg"),
            ("Uso", "Freio", "Bilateral"),
        ],
    ),
    (
        "Cama hospitalar",
        "CAMA",
        [
            ("Cama hospitalar manual", "Divicamas", 2400),
            ("Cama hospitalar 2 manivelas", "Divicamas", 2900),
            ("Cama hospitalar elétrica", "Carci", 6500),
            ("Cama hospitalar com grades", "Carci", 3100),
        ],
        [
            ("Medidas", "Comprimento", "1,90 m"),
            ("Recursos", "Grades laterais", "Sim"),
            ("Recursos", "Regulagem", "Cabeceira e pés"),
        ],
    ),
    (
        "Muleta",
        "MULETA",
        [
            ("Par de muletas axilares", "Ortobras", 120),
            ("Par de muletas canadenses", "Mobil", 150),
            ("Muleta axilar infantil", "Ortobras", 110),
            ("Par de muletas reguláveis", "Dellamed", 135),
        ],
        [("Medidas", "Altura regulável", "1,15 a 1,35 m"), ("Uso", "Capacidade máxima", "100 kg")],
    ),
    (
        "Cadeira de banho",
        "BANHO",
        [
            ("Cadeira de banho com rodas", "Carci", 690),
            ("Cadeira de banho fixa", "Mobil", 380),
            ("Cadeira higiênica dobrável", "Ortobras", 450),
        ],
        [
            ("Uso", "Capacidade máxima", "110 kg"),
            ("Material", "Estrutura", "Aço com pintura epóxi"),
        ],
    ),
    (
        "Bengala",
        "BENGALA",
        [
            ("Bengala de 4 pontas", "Mobil", 95),
            ("Bengala dobrável", "Ortobras", 70),
            ("Bengala com assento", "Dellamed", 160),
        ],
        [("Medidas", "Altura regulável", "72 a 95 cm")],
    ),
    (
        "Colchão",
        "COLCHAO",
        [
            ("Colchão pneumático", "Kestal", 260),
            ("Colchão caixa de ovo", "Ortobom", 140),
            ("Colchão hospitalar D33", "Ortobom", 420),
            ("Colchão de ar com compressor", "Kestal", 390),
            ("Colchão infantil hospitalar", "Ortobom", 300),
        ],
        [("Medidas", "Dimensões", "1,88 x 0,88 m"), ("Uso", "Indicação", "Prevenção de escaras")],
    ),
]

FIRST = [
    "Maria",
    "José",
    "Ana",
    "João",
    "Francisca",
    "Antônio",
    "Luzia",
    "Paulo",
    "Rita",
    "Carlos",
    "Helena",
    "Sebastião",
    "Cecília",
    "Geraldo",
    "Aparecida",
    "Raimundo",
]
LAST = [
    "Silva",
    "Souza",
    "Oliveira",
    "Lima",
    "Costa",
    "Pereira",
    "Rodrigues",
    "Almeida",
    "Ferreira",
    "Gomes",
    "Ribeiro",
    "Martins",
]
STREETS = [
    "Rua das Flores",
    "Rua Barão de Piumhi",
    "Avenida Brasil",
    "Rua Silviano Brandão",
    "Rua Juca Pinto",
    "Rua Aureliano Rodrigues",
]
NEIGHBOURHOODS = ["Centro", "Água Vermelha", "São Luiz", "Quinzinho", "Engenho de Serra"]


def fake_cpf(rng):
    first_nine = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return first_nine + cpf_check_digits(first_nine)


PHOTOS = Path(__file__).with_name("demo_images")  # real, openly licensed; see CREDITS.md there


def photos_for(code, n):
    """Up to two real photos of the category for its n-th item, rotating so items differ."""
    pool = sorted(PHOTOS.glob(f"{code.lower()}-*.jpg"))
    return [pool[(n + k) % len(pool)] for k in range(min(2, len(pool)))]


def contract_pdf(text):
    """A one-page PDF with `text`; offsets in the xref table are computed, so readers accept it."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return ContentFile(bytes(out), name="contrato.pdf")


class Command(BaseCommand):
    help = "Fill an EMPTY database with demo equipment, people, loans, contracts and logs."

    def handle(self, *args, **options):
        Equipment = apps.get_model("inventory", "Equipment")
        if Equipment.objects.exists() or Person.objects.exists():
            raise CommandError(
                "The database already has equipment or people. Run `manage.py flush` first."
            )
        with transaction.atomic():
            self.seed()
        self.stdout.write(self.style.SUCCESS(self.summary))

    def seed(self):
        rng = random.Random(42)  # same data on every run
        today = date.today()
        Warehouse = apps.get_model("inventory", "Warehouse")
        Category = apps.get_model("inventory", "Category")
        Equipment = apps.get_model("inventory", "Equipment")
        EquipmentImage = apps.get_model("inventory", "EquipmentImage")
        EquipmentSpec = apps.get_model("inventory", "EquipmentSpec")

        gestor = self.demo_user("gestor.demo", roles.MANAGER)
        atendente = self.demo_user("atendente.demo", roles.ATTENDANT)

        warehouses = [Warehouse.objects.create(name=n, address=a) for n, a in WAREHOUSES]
        items = []
        for category_name, code, products, specs in CATALOG:
            category = Category.objects.create(name=category_name, code=code)
            for n, (name, brand, value) in enumerate(products):
                item = Equipment.objects.create(
                    name=name,
                    brand=brand,
                    category=category,
                    warehouse=warehouses[n % 2],
                    description=f"{name} em bom estado, higienizado após cada empréstimo.",
                    value=value,
                    acquired_on=today - timedelta(days=200 + 37 * n),
                )
                for order, (section, label, spec_value) in enumerate(specs):
                    EquipmentSpec.objects.create(
                        equipment=item, section=section, label=label, value=spec_value, order=order
                    )
                # The last item of each category has no photo yet: staff see it, the public not.
                if n < len(products) - 1:
                    for order, path in enumerate(photos_for(code, n)):
                        EquipmentImage.objects.create(
                            equipment=item,
                            image=ContentFile(path.read_bytes(), name=path.name),
                            order=order,
                        )
                items.append(item)

        people = []
        for n in range(16):
            first, last = FIRST[n], rng.sample(LAST, 2)
            people.append(
                Person.objects.create(
                    name=f"{first} {last[0]} {last[1]}",
                    cpf=fake_cpf(rng),
                    birth_date=date(
                        1935 + rng.randint(0, 60), rng.randint(1, 12), rng.randint(1, 28)
                    ),
                    phone=f"(37) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
                    email=f"{first.lower()}.{last[0].lower()}@example.com" if n % 3 else "",
                    street=rng.choice(STREETS),
                    number=str(rng.randint(10, 999)),
                    neighborhood=rng.choice(NEIGHBOURHOODS),
                    city="Formiga",
                    state="MG",
                    cep="35570000",
                )
            )
        # people[0..3] are frequent Beneficiários, people[4..6] frequent Solidários, the
        # last two have no loans at all (they show only under Todas).

        def lend(item, borrower, guarantor, days_ago, term=180, by=atendente):
            loan = Loan.objects.create(
                equipment=item,
                person=borrower,
                guarantor=guarantor,
                lent_date=today - timedelta(days=days_ago),
                due_date=today - timedelta(days=days_ago) + timedelta(days=term),
            )
            LoanLog.record(loan, LoanLog.Action.LENT, by)
            return loan

        def give_back(loan, days_ago, by=atendente):
            loan.return_date = today - timedelta(days=days_ago)
            loan.save(update_fields=["return_date"])
            LoanLog.record(loan, LoanLog.Action.RETURNED, by)

        def attach(loan, by=atendente, replace=False):
            loan.contract.save("contrato.pdf", contract_pdf(f"Contrato emprestimo {loan.pk}"))
            action = LoanLog.Action.CONTRACT_REPLACED if replace else LoanLog.Action.CONTRACT_ADDED
            LoanLog.record(loan, action, by)

        p = people
        # Returned loans first (history), on items that may be lent again below.
        history = [
            (0, 0, 4, 400, 120),
            (1, 1, 5, 380, 200),
            (2, 2, 6, 350, 90),
            (3, 3, 4, 300, 150),
            (5, 0, 7, 260, 60),
            (8, 8, 5, 240, 100),
            (12, 1, 6, 220, 30),
            (15, 9, 4, 200, 20),
        ]
        for item_ix, borrower, guarantor, lent_ago, returned_ago in history:
            loan = lend(items[item_ix], p[borrower], p[guarantor], lent_ago)
            give_back(loan, returned_ago)
            attach(loan)

        # Open loans on time, some with the contract still pending.
        on_time = [
            (0, 10, 5, 40),
            (6, 2, 4, 25),
            (9, 11, 6, 70),
            (13, 3, 7, 10),
            (16, 12, 5, 5),
            (19, 0, 6, 15),
        ]
        for n, (item_ix, borrower, guarantor, lent_ago) in enumerate(on_time):
            loan = lend(items[item_ix], p[borrower], p[guarantor], lent_ago)
            if n % 2 == 0:
                attach(loan)
        # One contract was replaced after a signature was missing.
        attach(loan, replace=True)

        # Late loans: open and past the due date (the Solidário would be called).
        late = [(1, 1, 4, 220, 180), (10, 13, 5, 200, 120), (20, 2, 7, 95, 60)]
        for item_ix, borrower, guarantor, lent_ago, term in late:
            loan = lend(items[item_ix], p[borrower], p[guarantor], lent_ago, term=term)
        attach(loan)

        # A corrected loan: due date extended by the Gestor, with a reason.
        corrected = Loan.objects.filter(return_date__isnull=True).order_by("lent_date").first()
        old = {"due_date": corrected.due_date}
        corrected.due_date = corrected.due_date + timedelta(days=30)
        corrected.save(update_fields=["due_date"])
        LoanLog.record(
            corrected, LoanLog.Action.EDITED, gestor, old=old, reason="Família pediu mais 30 dias."
        )

        # Situações: one back from a loan with a defect, one in repair, one lost, one written off.
        defect = lend(items[22], p[3], p[6], 60)
        give_back(defect, 3)
        change_status(
            items[22].pk,
            "damaged",
            by=atendente,
            on=today - timedelta(days=3),
            reason="Devolvido com a roda dianteira quebrada.",
        )
        change_status(
            items[7].pk,
            "damaged",
            by=atendente,
            on=today - timedelta(days=20),
            reason="Manivela travando; enviada para conserto.",
        )
        change_status(
            items[17].pk,
            "lost",
            by=atendente,
            on=today - timedelta(days=45),
            reason="Beneficiário mudou de cidade e não devolveu.",
        )
        change_status(
            items[11].pk,
            "lost",
            by=atendente,
            on=today - timedelta(days=90),
            reason="Não encontrado no inventário.",
        )
        change_status(
            items[11].pk,
            "written_off",
            by=gestor,
            on=today - timedelta(days=60),
            reason="Extraviado há mais de 30 dias; baixa autorizada.",
        )

        self.summary = (
            f"Demo data: {len(items)} items, {len(people)} people, {Loan.objects.count()} loans "
            f"({Loan.objects.filter(contract='').count()} with contract pending). "
            "Demo users gestor.demo / atendente.demo have no password (log entries only)."
        )

    def demo_user(self, username, role):
        user = User.objects.create_user(username, first_name=username.split(".")[0].title())
        user.set_unusable_password()
        user.save()
        # `flush` also empties the role groups their migration created; bring them back.
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

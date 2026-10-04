"""The staff destinations: one list feeds the header menu and the staff home, so they never drift."""

from django.urls import reverse

from .access import is_manager, is_staff_member

# (label, url name, one-line description, icon, Gestor only)
ITEMS = [
    (
        "Equipamentos",
        "inventory:staff_equipment",
        "Todos os itens, com filtros e edição.",
        "grid",
        False,
    ),
    (
        "Cadastrar equipamento",
        "inventory:equipment_new",
        "Novo item com fotos e especificações.",
        "plus",
        False,
    ),
    (
        "Histórico",
        "lending:loans",
        "Empréstimos em aberto, atrasados e devolvidos.",
        "history",
        False,
    ),
    ("Pessoas", "lending:people", "Beneficiários e Solidários.", "users", False),
    (
        "Cadastrar pessoa",
        "lending:person_new",
        "Nova pessoa para emprestar ou garantir.",
        "plus",
        False,
    ),
    ("Catálogo público", "inventory:catalog", "O que o público vê.", "heart", False),
    ("Registros", "inventory:status_log", "Quem mudou o quê, e por quê.", "history", True),
    ("Admin", "admin:index", "Categorias, depósitos e contas da equipe.", "settings", True),
]


def menu_items(user):
    """Destinations this user may open; empty for anyone outside the staff."""
    if not user.is_authenticated or not is_staff_member(user):
        return []
    manager = is_manager(user)
    return [
        {"label": label, "url": reverse(name), "description": text, "icon": icon}
        for label, name, text, icon, manager_only in ITEMS
        if manager or not manager_only
    ]

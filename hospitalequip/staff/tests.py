import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from hospitalequip.staff import roles


@pytest.mark.django_db
def test_role_names_in_code_match_groups_in_database():
    assert set(Group.objects.values_list("name", flat=True)) >= {roles.ATTENDANT, roles.MANAGER}


@pytest.mark.django_db
def test_staff_area_sends_anonymous_visitors_to_login(client):
    response = client.get(reverse("staff:home"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("staff:login"))


@pytest.mark.django_db
def test_login_lands_on_staff_area(client):
    user = User.objects.create_user("ana", password="senha-forte-123")
    user.groups.add(Group.objects.get(name=roles.ATTENDANT))
    response = client.post(
        reverse("staff:login"), {"username": "ana", "password": "senha-forte-123"}
    )
    assert response.url == reverse("staff:home")
    assert client.get(response.url).status_code == 200


# Rule: one staff menu feeds the header and the home; Gestor-only items show only to the Gestor.


def menu_labels(client):
    return [item["label"] for item in client.get(reverse("staff:home")).context["staff_menu"]]


def login_as(client, role):
    user = User.objects.create_user(role, password="x")
    user.groups.add(Group.objects.get(name=role))
    client.force_login(user)


@pytest.mark.django_db
def test_attendant_menu_leaves_out_gestor_items(client):
    login_as(client, roles.ATTENDANT)
    labels = menu_labels(client)
    assert "Pessoas" in labels and "Equipamentos" in labels
    assert "Registros" not in labels and "Admin" not in labels


@pytest.mark.django_db
def test_gestor_menu_has_registros(client):
    login_as(client, roles.MANAGER)
    assert "Registros" in menu_labels(client)


@pytest.mark.django_db
def test_staff_home_shows_every_menu_destination(client):
    login_as(client, roles.ATTENDANT)
    response = client.get(reverse("staff:home"))
    page = response.content.decode()
    for item in response.context["staff_menu"]:
        assert page.count(f'href="{item["url"]}"') >= 2  # header menu and home card


@pytest.mark.django_db
def test_visitors_and_non_staff_get_no_menu(client):
    assert client.get(reverse("inventory:catalog")).context["staff_menu"] == []
    client.force_login(User.objects.create_user("visitante", password="x"))
    assert client.get(reverse("inventory:catalog")).context["staff_menu"] == []

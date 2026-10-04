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

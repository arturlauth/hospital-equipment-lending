from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.home, name="home"),
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
]

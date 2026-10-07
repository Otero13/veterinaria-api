from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("especialidades", views.EspecialidadViewSet, basename="especialidad")
router.register("veterinarios", views.VeterinarioViewSet, basename="veterinario")
router.register("mascotas", views.MascotaViewSet, basename="mascota")
router.register("citas", views.CitaViewSet, basename="cita")

urlpatterns = [
    path("salud/", views.SaludView.as_view(), name="salud"),
    path("auth/registro/", views.RegistroView.as_view(), name="registro"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MiPerfilView.as_view(), name="me"),
    path("", include(router.urls)),
]

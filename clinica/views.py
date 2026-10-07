import logging

from django.contrib.auth import get_user_model
from rest_framework import generics, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Cita, Especialidad, Mascota, Perfil
from .permissions import (
    ADMIN, CLIENTE, VETERINARIO, PermisoCita, PermisoMascota, SoloAdminEscritura, obtener_rol,
)
from .serializers import (
    CitaSerializer, EspecialidadSerializer, MascotaSerializer, PerfilSerializer,
    RegistroSerializer,
)

logger = logging.getLogger("clinica")
User = get_user_model()


# ---------------------------------------------------------- Autenticación
class SaludView(APIView):
    """GET /api/v1/salud/ - comprueba que la API está arriba (sin autenticación)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"estado": "API operativa"})


class RegistroView(generics.CreateAPIView):
    """POST /api/v1/auth/registro/ - crea un usuario con rol CLIENTE."""

    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registro"


class LoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ - entrega access + refresh. Limitado contra fuerza bruta."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            # Queda registrado para detectar intentos de fuerza bruta
            logger.warning("Login fallido para usuario=%s", request.data.get("username"))
            raise


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ - invalida (blacklist) el refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"refresh": ["Este campo es obligatorio."]}, status=400)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"refresh": ["Token inválido o expirado."]}, status=400)
        return Response({"detalle": "Sesión cerrada correctamente."}, status=200)


class MiPerfilView(APIView):
    """GET /api/v1/auth/me/ - datos del usuario autenticado."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = Perfil.objects.select_related("usuario").filter(usuario=request.user).first()
        if perfil is None:
            return Response({"detail": "El usuario no tiene perfil."}, status=404)
        return Response(PerfilSerializer(perfil).data)


# ------------------------------------------------------------------ CRUD
class EspecialidadViewSet(viewsets.ModelViewSet):
    """Lectura para cualquier usuario autenticado; escritura solo ADMIN."""

    queryset = Especialidad.objects.all()
    serializer_class = EspecialidadSerializer
    permission_classes = [IsAuthenticated, SoloAdminEscritura]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["nombre"]
    ordering = ["nombre"]


class VeterinarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Listado de veterinarios (para que los clientes sepan con quién agendar)."""

    serializer_class = PerfilSerializer
    permission_classes = [IsAuthenticated, SoloAdminEscritura]
    filter_backends = [SearchFilter]
    search_fields = ["usuario__username", "especialidades__nombre"]

    def get_queryset(self):
        return (
            Perfil.objects.filter(rol=Perfil.Rol.VETERINARIO)
            .select_related("usuario")
            .prefetch_related("especialidades")
            .order_by("id")
            .distinct()
        )


class MascotaViewSet(viewsets.ModelViewSet):
    serializer_class = MascotaSerializer
    permission_classes = [IsAuthenticated, PermisoMascota]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["nombre", "raza"]
    ordering_fields = ["nombre", "creada_en"]
    ordering = ["id"]

    def get_queryset(self):
        usuario = self.request.user
        rol = obtener_rol(usuario)
        qs = Mascota.objects.select_related("duenio")
        if rol == ADMIN:
            return qs
        if rol == VETERINARIO:
            return qs.filter(citas__veterinario=usuario).distinct()
        if rol == CLIENTE:
            return qs.filter(duenio=usuario)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(duenio=self.request.user)


class CitaViewSet(viewsets.ModelViewSet):
    serializer_class = CitaSerializer
    permission_classes = [IsAuthenticated, PermisoCita]
    filter_backends = [OrderingFilter]
    ordering_fields = ["fecha_hora", "estado"]
    ordering = ["fecha_hora"]

    def get_queryset(self):
        usuario = self.request.user
        rol = obtener_rol(usuario)
        qs = Cita.objects.select_related("mascota", "veterinario")
        if rol == ADMIN:
            pass
        elif rol == VETERINARIO:
            qs = qs.filter(veterinario=usuario)
        elif rol == CLIENTE:
            qs = qs.filter(mascota__duenio=usuario)
        else:
            return qs.none()

        # Filtro opcional ?estado=PENDIENTE (solo se aplica si el valor es válido)
        estado = self.request.query_params.get("estado", "").upper()
        if estado in Cita.Estado.values:
            qs = qs.filter(estado=estado)
        return qs

    def perform_create(self, serializer):
        # Toda cita nueva nace PENDIENTE, sin importar lo que envíe el cliente
        serializer.save(estado=Cita.Estado.PENDIENTE)

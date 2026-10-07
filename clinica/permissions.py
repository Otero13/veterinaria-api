"""Permisos personalizados basados en el rol del usuario."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Perfil

ADMIN = Perfil.Rol.ADMIN
VETERINARIO = Perfil.Rol.VETERINARIO
CLIENTE = Perfil.Rol.CLIENTE


def obtener_rol(user):
    """Devuelve el rol del usuario o None si no tiene perfil."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    try:
        return user.perfil.rol
    except Perfil.DoesNotExist:
        return None


class SoloAdminEscritura(BasePermission):
    """Cualquier usuario con rol puede leer; solo el ADMIN puede crear/editar/borrar."""

    def has_permission(self, request, view):
        rol = obtener_rol(request.user)
        if rol is None:
            return False
        return request.method in SAFE_METHODS or rol == ADMIN


class PermisoMascota(BasePermission):
    """
    - ADMIN: todo.
    - CLIENTE: crea mascotas y gestiona solo las suyas.
    - VETERINARIO: solo lectura (y solo de mascotas con las que tiene citas).
    """

    def has_permission(self, request, view):
        rol = obtener_rol(request.user)
        if rol is None:
            return False
        if rol == VETERINARIO:
            return request.method in SAFE_METHODS
        return True

    def has_object_permission(self, request, view, obj):
        rol = obtener_rol(request.user)
        if rol == ADMIN:
            return True
        if rol == CLIENTE:
            return obj.duenio_id == request.user.id
        return request.method in SAFE_METHODS


class PermisoCita(BasePermission):
    """
    - ADMIN: todo.
    - CLIENTE: agenda citas para sus mascotas y puede cancelarlas; no puede borrarlas.
    - VETERINARIO: solo ve y actualiza el estado de sus propias citas.
    """

    def has_permission(self, request, view):
        rol = obtener_rol(request.user)
        if rol is None:
            return False
        if request.method == "DELETE":
            return rol == ADMIN
        if request.method == "POST":
            return rol in (ADMIN, CLIENTE)
        return True

    def has_object_permission(self, request, view, obj):
        rol = obtener_rol(request.user)
        if rol == ADMIN:
            return True
        if rol == CLIENTE:
            return obj.mascota.duenio_id == request.user.id
        if rol == VETERINARIO:
            return obj.veterinario_id == request.user.id
        return False

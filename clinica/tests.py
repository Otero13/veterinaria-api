from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Cita, Especialidad, Mascota, Perfil

User = get_user_model()
CLAVE = "ClaveSegura#2026"
BASE = "/api/v1"


def crear_usuario(username, rol):
    user = User.objects.create_user(username, f"{username}@test.cl", CLAVE)
    Perfil.objects.create(usuario=user, rol=rol)
    return user


class BaseAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia los contadores de rate limiting
        self.admin = crear_usuario("admin_test", Perfil.Rol.ADMIN)
        self.vet = crear_usuario("vet_test", Perfil.Rol.VETERINARIO)
        self.cliente = crear_usuario("cliente1", Perfil.Rol.CLIENTE)
        self.otro = crear_usuario("cliente2", Perfil.Rol.CLIENTE)
        self.mascota = Mascota.objects.create(duenio=self.cliente, nombre="Rex", especie="PERRO")
        self.mascota_ajena = Mascota.objects.create(duenio=self.otro, nombre="Misu", especie="GATO")
        self.manana = timezone.now() + timedelta(days=1)

    def datos_cita(self, **extra):
        datos = {
            "mascota": self.mascota.id,
            "veterinario": self.vet.id,
            "fecha_hora": self.manana.isoformat(),
            "motivo": "Control general",
        }
        datos.update(extra)
        return datos


class AutenticacionTests(BaseAPITest):
    def test_registro_crea_cliente_aunque_envie_rol(self):
        r = self.client.post(f"{BASE}/auth/registro/", {
            "username": "nuevo_user", "email": "nuevo@test.cl",
            "password": CLAVE, "password2": CLAVE, "rol": "ADMIN",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["datos"]["rol"], "CLIENTE")
        self.assertNotIn("password", r.json()["datos"])

    def test_registro_con_claves_distintas_da_400(self):
        r = self.client.post(f"{BASE}/auth/registro/", {
            "username": "otro_user", "email": "otro@test.cl",
            "password": CLAVE, "password2": "OtraClave#2026",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_login_entrega_tokens(self):
        r = self.client.post(f"{BASE}/auth/login/", {"username": "cliente1", "password": CLAVE}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json()["datos"])
        self.assertIn("refresh", r.json()["datos"])

    def test_login_incorrecto_da_401(self):
        r = self.client.post(f"{BASE}/auth/login/", {"username": "cliente1", "password": "mala"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_login_tiene_rate_limiting(self):
        codigos = [
            self.client.post(f"{BASE}/auth/login/", {"username": "cliente1", "password": "mala"}, format="json").status_code
            for _ in range(10)
        ]
        self.assertIn(429, codigos)

    def test_endpoint_protegido_sin_token_da_401(self):
        self.assertEqual(self.client.get(f"{BASE}/mascotas/").status_code, 401)

    def test_logout_invalida_refresh(self):
        login = self.client.post(f"{BASE}/auth/login/", {"username": "cliente1", "password": CLAVE}, format="json").json()["datos"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
        r = self.client.post(f"{BASE}/auth/logout/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"{BASE}/auth/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(r.status_code, 401)


class MascotaTests(BaseAPITest):
    def test_cliente_solo_ve_sus_mascotas(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.get(f"{BASE}/mascotas/")
        self.assertEqual(r.status_code, 200)
        nombres = [m["nombre"] for m in r.json()["datos"]["results"]]
        self.assertEqual(nombres, ["Rex"])

    def test_cliente_no_accede_a_mascota_ajena(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(f"{BASE}/mascotas/{self.mascota_ajena.id}/").status_code, 404)

    def test_crear_mascota_sanitiza_html(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(f"{BASE}/mascotas/", {"nombre": "<b>Toby</b>", "especie": "PERRO"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["datos"]["nombre"], "Toby")
        self.assertEqual(r.json()["datos"]["duenio"], self.cliente.id)

    def test_fecha_nacimiento_futura_da_400(self):
        self.client.force_authenticate(self.cliente)
        futura = (timezone.localdate() + timedelta(days=5)).isoformat()
        r = self.client.post(f"{BASE}/mascotas/", {"nombre": "Toby", "fecha_nacimiento": futura}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_veterinario_no_puede_crear_mascotas(self):
        self.client.force_authenticate(self.vet)
        r = self.client.post(f"{BASE}/mascotas/", {"nombre": "Toby"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_eliminar_mascota_propia_da_204(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.delete(f"{BASE}/mascotas/{self.mascota.id}/").status_code, 204)


class CitaTests(BaseAPITest):
    def test_cliente_agenda_cita_pendiente(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(f"{BASE}/citas/", self.datos_cita(estado="CANCELADA"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["datos"]["estado"], "PENDIENTE")

    def test_cita_en_el_pasado_da_400(self):
        self.client.force_authenticate(self.cliente)
        pasado = (timezone.now() - timedelta(days=1)).isoformat()
        r = self.client.post(f"{BASE}/citas/", self.datos_cita(fecha_hora=pasado), format="json")
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_agendar_para_mascota_ajena(self):
        self.client.force_authenticate(self.cliente)
        r = self.client.post(f"{BASE}/citas/", self.datos_cita(mascota=self.mascota_ajena.id), format="json")
        self.assertEqual(r.status_code, 400)

    def test_veterinario_ocupado_da_400(self):
        Cita.objects.create(mascota=self.mascota_ajena, veterinario=self.vet,
                            fecha_hora=self.manana, motivo="Vacuna")
        self.client.force_authenticate(self.cliente)
        r = self.client.post(f"{BASE}/citas/", self.datos_cita(), format="json")
        self.assertEqual(r.status_code, 400)

    def test_cliente_cancela_su_cita(self):
        cita = Cita.objects.create(mascota=self.mascota, veterinario=self.vet,
                                   fecha_hora=self.manana, motivo="Control")
        self.client.force_authenticate(self.cliente)
        r = self.client.patch(f"{BASE}/citas/{cita.id}/", {"estado": "CANCELADA"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["datos"]["estado"], "CANCELADA")

    def test_cliente_no_puede_confirmar_su_cita(self):
        cita = Cita.objects.create(mascota=self.mascota, veterinario=self.vet,
                                   fecha_hora=self.manana, motivo="Control")
        self.client.force_authenticate(self.cliente)
        r = self.client.patch(f"{BASE}/citas/{cita.id}/", {"estado": "CONFIRMADA"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_veterinario_confirma_pero_no_edita_otros_campos(self):
        cita = Cita.objects.create(mascota=self.mascota, veterinario=self.vet,
                                   fecha_hora=self.manana, motivo="Control")
        self.client.force_authenticate(self.vet)
        ok = self.client.patch(f"{BASE}/citas/{cita.id}/", {"estado": "CONFIRMADA"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        mal = self.client.patch(f"{BASE}/citas/{cita.id}/", {"motivo": "Otro motivo"}, format="json")
        self.assertEqual(mal.status_code, 400)

    def test_veterinario_no_puede_crear_cita(self):
        self.client.force_authenticate(self.vet)
        self.assertEqual(self.client.post(f"{BASE}/citas/", self.datos_cita(), format="json").status_code, 403)

    def test_solo_admin_elimina_citas(self):
        cita = Cita.objects.create(mascota=self.mascota, veterinario=self.vet,
                                   fecha_hora=self.manana, motivo="Control")
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.delete(f"{BASE}/citas/{cita.id}/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"{BASE}/citas/{cita.id}/").status_code, 204)


class EspecialidadTests(BaseAPITest):
    def test_cliente_lee_pero_no_crea(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(f"{BASE}/especialidades/").status_code, 200)
        r = self.client.post(f"{BASE}/especialidades/", {"nombre": "Cirugía"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_admin_crea_y_recurso_inexistente_da_404(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"{BASE}/especialidades/", {"nombre": "Cirugía"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Especialidad.objects.filter(nombre="Cirugía").exists())
        self.assertEqual(self.client.get(f"{BASE}/especialidades/9999/").status_code, 404)

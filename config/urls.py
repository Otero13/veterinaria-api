   from django.contrib import admin
   from django.urls import include, path
   from django.views.generic import TemplateView

   urlpatterns = [
       path("", TemplateView.as_view(template_name="clinica/index.html"), name="inicio"),
       path("admin/", admin.site.urls),
       path("api/v1/", include("clinica.urls")),
   ]

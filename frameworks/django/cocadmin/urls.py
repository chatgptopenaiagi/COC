from django.contrib import admin
from django.urls import path
from . import views
urlpatterns=[path("admin/",admin.site.urls),path("",views.overview),path("api/snapshot",views.snapshot),path("api/control",views.control)]

from django.urls import path
from agenda import views
urlpatterns = [path('api/<str:action>', views.api), path('',views.index), path('ativar',views.index)]

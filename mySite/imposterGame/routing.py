# imposterGame/routing.py
from django.urls import path
from .consumers import LobbyConsumer

websocket_urlpatterns = [
    path('ws/room/<str:room_id>/', LobbyConsumer.as_asgi()),
]


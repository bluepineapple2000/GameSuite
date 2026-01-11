# imposterGame/urls.py

from django.urls import path
from . import views

app_name = "imposterGame"

urlpatterns = [
    path("select-name/", views.select_name, name="select_name"),
    path("", views.home, name="imposter_home"),
    path("create-room/", views.create_room, name="create_room"),
    path("join-room/", views.join_room, name="join_room"),
    path("room/<str:room_id>/", views.room, name="room"),
    path("start-round/<str:room_id>/", views.start_round, name="start_round"),
    path("kick-player/<str:room_id>/", views.kick_player, name="kick_player"),
    path("leave-room/<str:room_id>/", views.leave_room, name="leave_room"),
    
]

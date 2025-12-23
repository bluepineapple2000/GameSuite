from django.shortcuts import redirect, render

from .models import Room


def home(request):
    return render(request, "home.html")


def create_room(request):
    room_id = Room.generate_room_id()
    Room.objects.create(room_id=room_id)
    return redirect("room", room_id=room_id)


def join_room(request):
    if request.method == "POST":
        room_id = request.POST.get("room_id", "").upper()
        try:
            Room.objects.get(room_id=room_id)
            return redirect("room", room_id=room_id)
        except Room.DoesNotExist:
            return render(
                request,
                "join_room.html",
                {"error": "Room not found"},
            )

    return render(request, "join_room.html")


def room(request, room_id):
    room = Room.objects.get(room_id=room_id)

    # Get player from session or request
    player_name = request.session.get("player_name")

    if not player_name:
        player_name = request.GET.get("name")
        if player_name:
            request.session["player_name"] = player_name
            return redirect("room", room_id=room_id)

    # Add player once
    if player_name and player_name not in room.players:
        room.players.append(player_name)
        room.save()

    role = None
    if room.imposter:
        role = "IMPOSTER" if player_name == room.imposter else room.word

    return render(
        request,
        "room.html",
        {
            "room": room,
            "player": player_name,
            "role": role,
        },
    )


def start_round(request, room_id):
    room = Room.objects.get(room_id=room_id)
    room.choose_round()
    return redirect("room", room_id=room_id)

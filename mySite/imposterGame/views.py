import random
from django.shortcuts import redirect, render, get_object_or_404
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Room, WORDS, Player


def home(request):
    player_id = request.session.get("player_id")

    if not player_id:
        return redirect("imposterGame:select_name")

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        del request.session["player_id"]
        return redirect("imposterGame:select_name")

    return render(request, "imposter_home.html", {
        "player": player
    })


def select_name(request): 
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if name:
            player = Player.objects.create(name=name)
            request.session["player_id"] = player.id  # 👈 remember player
            return redirect("imposterGame:imposter_home")

    return render(request, "select_name.html")

def create_room(request):
    # 1️⃣ Get current player from session
    player_id = request.session.get("player_id")
    print("Player ID:", player_id)
    if not player_id:
        return redirect("imposterGame:select_name")

    try: 
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        del request.session["player_id"]
        return redirect("imposterGame:select_name")
    print("Player:", player)    

    room_id = Room.generate_room_id()
    print("Generated Room ID:", room_id)

    room = Room.objects.create(room_id=room_id)

    # 3️⃣ Assign player to room
    player.room = room
    player.save()

    # 4️⃣ Redirect to the room page
    return redirect("imposterGame:room", room_id=room.room_id)

def join_room(request):
    player_id = request.session.get("player_id")
    if not player_id:
        return redirect("imposterGame:select_name")

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        del request.session["player_id"]
        return redirect("imposterGame:select_name")

    error = None

    if request.method == "POST":
        room_id = request.POST.get("room_id", "").strip()
        name = player.name.strip()

        # 1️⃣ Check if room exists
        try:
            room = Room.objects.get(room_id=room_id)
        except Room.DoesNotExist:
            error = f"Room {room_id} does not exist."
            room = None

        if room:
            # 2️⃣ Ensure unique username in this room
            existing_names = room.players.values_list('name', flat=True)
            new_name = name
            counter = 1
            while new_name in existing_names:
                counter += 1
                new_name = f"{name}{counter}"

            player.name = new_name
            player.room = room
            player.save()

            return redirect("imposterGame:room", room_id=room.room_id)

    return render(request, "join_room.html", {"error": error})

def room(request, room_id):
    # 1️⃣ Get the room
    room = get_object_or_404(Room, room_id=room_id)

    # 2️⃣ Get current player from session
    player_id = request.session.get("player_id")
    if not player_id:
        return redirect("imposterGame:select_name")

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        del request.session["player_id"]
        return redirect("imposterGame:select_name")
    
    players_in_room = room.players.all()

    role = None
    if room.word:
        if player in room.imposter.all():
            role = "IMPOSTER"
        else:
            role = room.word

    return render(
        request,
        "room.html",
        {
            "room": room,
            "player": player,
            "players": players_in_room,
            'role': role,
        },
    )

def leave_room(request, room_id):
    # Get current player from session
    player_id = request.session.get("player_id")
    if player_id:
        try:
            player = Player.objects.get(id=player_id)
            # Only remove player if they are in this room
            player.room = None
            player.save()
        except Player.DoesNotExist:
            # If player not found, clear session
            del request.session["player_id"]
    
    # Redirect to home page after leaving
    return redirect("home")

def kick_player(request, room_id):
    #Get current player from session
    player_id = request.session.get("player_id")
    if not player_id:
        return redirect("imposterGame:home")

    current_player = get_object_or_404(Player, id=player_id)

    # Get the room
    room = get_object_or_404(Room, room_id=room_id)

    # Only allow kicking if current player is in the room
    if current_player.room != room:
        return redirect("imposterGame:room", room_id=room_id)

    error = None

    if request.method == "POST":
        # Get the ID of the player to kick from form
        target_player_id = request.POST.get("player_id")
        if target_player_id:
            try:
                target_player = Player.objects.get(id=target_player_id, room=room)
                target_player.room = None
                target_player.save()
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"room_{room_id}",
                    {"type": "player_kicked"}
                )
                return redirect("imposterGame:room", room_id=room_id)
            except Player.DoesNotExist:
                error = "Player not found in this room."

    # Show a form with all players except current player
    other_players = room.players.exclude(id=current_player.id)

    return render(
        request,
        "kick_player.html",
        {"room": room, "players": other_players, "error": error},
    )


def start_round(request, room_id):
    room = get_object_or_404(Room, room_id=room_id)

    players = list(Player.objects.filter(room=room))
    player_count = len(players)

    if player_count < 3:
        # Optional: minimum players check
        return redirect("imposterGame:room", room_id=room_id)

    # Decide number of imposters
    imposter_count = 2 if player_count > 6 else 1

    imposters = random.sample(players, imposter_count)
    word = random.choice(WORDS)

    # Save room state
    room.imposter.clear()
    room.imposter.add(*imposters)
    room.word = word
    room.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"room_{room_id}",
        {"type": "next_round", "players":get_players(room.room_id)}
    )

    return redirect("imposterGame:room", room_id=room_id)

def get_players(room_id):
        room = Room.objects.get(room_id=room_id)
        return list(room.players.values_list("name", flat=True))

import secrets

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django import forms
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from gameAI.forms import CategoryForm
from gameAI.service import GenerationError, generate, generation_slot, normalize

from .models import Player, Room, UsedWord


class NameForm(forms.Form):
    name = forms.CharField(max_length=50, strip=True)


class JoinForm(forms.Form):
    room_id = forms.IntegerField(min_value=1, max_value=99999999)


def current_player(request):
    return Player.objects.filter(pk=request.session.get("player_id")).first()


def member(request, room_id):
    room = get_object_or_404(Room, room_id=room_id)
    player = current_player(request)
    if not player or player.room_id != room.pk:
        return room, None
    return room, player


def notify(room):
    # Never send a secret word, role or private identifier over a group channel.
    async_to_sync(get_channel_layer().group_send)(
        f"room_{room.room_id}",
        {"type": "lobby_changed"},
    )


def home(request):
    player = current_player(request)
    if not player:
        return redirect("imposterGame:select_name")
    return render(request, "imposter_home.html", {"player": player})


def select_name(request):
    form = NameForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if current_player(request):
            return redirect("imposterGame:imposter_home")
        player = Player.objects.create(name=form.cleaned_data["name"])
        request.session.cycle_key()
        request.session["player_id"] = player.pk
        return redirect("imposterGame:imposter_home")
    return render(request, "select_name.html", {"form": form})


@require_POST
def create_room(request):
    player = current_player(request)
    if not player:
        return redirect("imposterGame:select_name")
    if player.room_id:
        return redirect("imposterGame:room", room_id=player.room.room_id)
    for _ in range(5):
        try:
            with transaction.atomic():
                room = Room.objects.create(room_id=Room.generate_room_id(), host=player)
                player.room = room
                player.save(update_fields=["room"])
            return redirect("imposterGame:room", room_id=room.room_id)
        except IntegrityError:
            continue
    return render(request, "join_room.html", {"error": "Please try again."}, status=503)


def join_room(request):
    player = current_player(request)
    if not player:
        return redirect("imposterGame:select_name")
    error = None
    form = JoinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = Room.objects.filter(room_id=form.cleaned_data["room_id"]).first()
        if not room:
            error = "Room not found. Check your invitation code."
        elif player.room_id:
            return redirect("imposterGame:room", room_id=player.room.room_id)
        else:
            try:
                with transaction.atomic():
                    if room.players.count() >= 20:
                        error = "This room is full."
                    else:
                        # Never mutate a player's name based on unbounded suffix growth.
                        if room.players.filter(name=player.name).exists():
                            player.name = f"{player.name[:40]}-{secrets.token_hex(3)}"
                        player.room = room
                        player.save(update_fields=["room", "name"])
                if not error:
                    notify(room)
                    return redirect("imposterGame:room", room_id=room.room_id)
            except IntegrityError:
                error = "Please try joining again."
    return render(request, "join_room.html", {"error": error, "form": form})


def room(request, room_id):
    room, player = member(request, room_id)
    if not player:
        return HttpResponseForbidden("Room membership required.")
    role = None
    if room.word:
        role = "IMPOSTER" if room.imposter.filter(pk=player.pk).exists() else room.word
    return render(
        request,
        "room.html",
        {
            "room": room,
            "player": player,
            "players": room.players.all(),
            "role": role,
            "is_host": room.host_id == player.pk,
            "form": CategoryForm(initial={"category": room.category}),
        },
    )


@require_POST
def leave_room(request, room_id):
    room, player = member(request, room_id)
    if not player:
        return HttpResponseForbidden("Room membership required.")
    with transaction.atomic():
        room.imposter.remove(player)
        player.room = None
        player.save(update_fields=["room"])
        if room.host_id == player.pk:
            room.host = room.players.order_by("id").first()
            room.save(update_fields=["host"])
        if not room.players.exists():
            room.delete()
    notify(room)
    return redirect("imposterGame:imposter_home")


def kick_player(request, room_id):
    room, player = member(request, room_id)
    if not player or room.host_id != player.pk:
        return HttpResponseForbidden("Only the room host may remove players.")
    error = None
    if request.method == "POST":
        target_id = request.POST.get("player_id", "")
        target = (
            room.players.exclude(pk=player.pk).filter(pk=int(target_id)).first()
            if target_id.isascii() and target_id.isdigit() and len(target_id) <= 10
            else None
        )
        if target:
            with transaction.atomic():
                room.imposter.remove(target)
                target.room = None
                target.save(update_fields=["room"])
            notify(room)
            return redirect("imposterGame:room", room_id=room_id)
        error = "Player not found in this room."
    return render(
        request,
        "kick_player.html",
        {
            "room": room,
            "players": room.players.exclude(pk=player.pk),
            "error": error,
        },
    )


@require_POST
def start_round(request, room_id):
    room, player = member(request, room_id)
    if not player or room.host_id != player.pk:
        return HttpResponseForbidden("Only the room host may start a round.")
    form = CategoryForm(request.POST)
    if not form.is_valid():
        return render(request, "round_error.html", {"room": room, "error": form.errors}, status=400)
    if room.players.count() < 3:
        return render(
            request,
            "round_error.html",
            {"room": room, "error": "At least three players are needed."},
            status=400,
        )
    try:
        with generation_slot():
            history = list(room.used_words.values_list("word", flat=True))
            word = generate("word", form.cleaned_data["category"], history)
            with transaction.atomic():
                # Membership may change while the provider is generating.
                room.refresh_from_db()
                players = list(room.players.all())
                if (
                    room.host_id != player.pk
                    or not any(p.pk == player.pk for p in players)
                    or len(players) < 3
                ):
                    raise GenerationError("The room changed. Please try again.")
                UsedWord.objects.create(room=room, word=word, normalized=normalize(word))
                room.word = word
                room.category = form.cleaned_data["category"]
                room.save(update_fields=["word", "category"])
                room.imposter.set(
                    secrets.SystemRandom().sample(players, 2 if len(players) > 6 else 1)
                )
        notify(room)
    except (GenerationError, Room.DoesNotExist) as exc:
        error = str(exc) if isinstance(exc, GenerationError) else "The room has closed."
        return render(request, "round_error.html", {"room": room, "error": error}, status=503)
    return redirect("imposterGame:room", room_id=room_id)

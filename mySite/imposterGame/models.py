import random
import uuid

from django.db import models

WORDS = [
    "Apple",
    "Bridge",
    "Castle",
    "Dragon",
    "Forest",
    "Guitar",
    "Island",
    "Meteor",
    "Pirate",
    "Robot",
]

class Player(models.Model):
    name = models.CharField(max_length=50)
    room = models.ForeignKey(
        "Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="players"
    )

    class Meta:
        unique_together = ("room", "name")

    def __str__(self):
        return self.name



class Room(models.Model):
    room_id = models.IntegerField(unique=True)
    imposter = models.ManyToManyField(Player, blank=True, related_name="imposter_in_rooms")
    word = models.CharField(max_length=50, blank=True)

    @staticmethod
    def generate_room_id():
        room_id = 1
        while True:
            if not Room.objects.filter(room_id=room_id).exists():
                return room_id
            room_id += 1

    



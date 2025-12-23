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


class Room(models.Model):
    room_id = models.CharField(max_length=8, unique=True)
    players = models.JSONField(default=list)  # list of player names
    imposter = models.CharField(max_length=50, blank=True)
    word = models.CharField(max_length=50, blank=True)

    def choose_round(self):
        if not self.players:
            return
        self.imposter = random.choice(self.players)
        self.word = random.choice(WORDS)
        self.save()

    @staticmethod
    def generate_room_id():
        return uuid.uuid4().hex[:8].upper()

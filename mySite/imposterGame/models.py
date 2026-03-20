import random
import uuid
import csv
import os
from django.db import models

# Load words from word.csv
def load_words():
    words = []
    csv_path = os.path.join(os.path.dirname(__file__), "word.csv")
    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    words.append(row[0].strip())
    except Exception:
        pass
    return words

WORDS = load_words()

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

    



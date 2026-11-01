import secrets

from django.db import models


class Player(models.Model):
    name = models.CharField(max_length=50)
    room = models.ForeignKey(
        "Room", on_delete=models.SET_NULL, null=True, blank=True, related_name="players"
    )

    class Meta:
        unique_together = ("room", "name")

    def __str__(self):
        return self.name


class Room(models.Model):
    room_id = models.IntegerField(unique=True)
    imposter = models.ManyToManyField(Player, blank=True, related_name="imposter_in_rooms")
    word = models.CharField(max_length=50, blank=True)

    host = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name="hosted_rooms"
    )
    category = models.CharField(max_length=120, blank=True)

    @staticmethod
    def generate_room_id():
        while True:
            room_id = secrets.randbelow(90000000) + 10000000
            if not Room.objects.filter(room_id=room_id).exists():
                return room_id


class UsedWord(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="used_words")
    word = models.CharField(max_length=50)
    normalized = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "normalized"], name="unique_room_word")
        ]
        ordering = ["id"]

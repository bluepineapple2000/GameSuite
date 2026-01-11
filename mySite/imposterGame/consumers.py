# imposterGame/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async

from .models import Room

class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"room_{self.room_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

    @database_sync_to_async
    def get_players(self):
        room = Room.objects.get(room_id=self.room_id)
        return list(room.players.values_list("name", flat=True))

    # Receive messages from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get("event")

        # Broadcast join / leave / kick messages
        if event_type == "player_joined":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "player_joined", "players": await self.get_players()}
            )
        elif event_type == "player_kicked":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "player_kicked", "players": await self.get_players()}
            )
        elif event_type == "player_left":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "player_left", "players": await self.get_players()}
            )
        elif event_type == "next_round":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "next_round", "players": await self.get_players()}
            )
    # Handle join broadcast
    async def player_joined(self, event):
        await self.send(text_data=json.dumps({"event": "player_joined", "players": event["players"]}))
    # Handle leave broadcast
    async def player_left(self, event):
        await self.send(text_data=json.dumps({"event": "player_left", "players": event["players"]}))

    # Handle kicked broadcast
    async def player_kicked(self, event):
        await self.send(text_data=json.dumps({"event": "player_kicked", "players": event["players"]}))
    async def next_round(self, event):
        await self.send(text_data=json.dumps({"event": "next_round", "players": event["players"]}))

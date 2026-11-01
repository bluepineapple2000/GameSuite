import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Player


class LobbyConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def is_member(self):
        return Player.objects.filter(
            pk=self.scope["session"].get("player_id"),
            room__room_id=self.room_id,
        ).exists()

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"room_{self.room_id}"
        if not await self.is_member():
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients cannot trigger group events or request private game state.
        await self.close(code=4400)

    async def lobby_changed(self, event):
        if not await self.is_member():
            await self.close(code=4403)
            return
        await self.send(text_data=json.dumps({"event": "lobby_changed"}))

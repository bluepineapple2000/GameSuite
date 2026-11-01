from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.test import Client, TestCase, TransactionTestCase, override_settings

from .consumers import LobbyConsumer
from .models import Player, Room, UsedWord


@override_settings(SECURE_SSL_REDIRECT=False)
class RoomTests(TestCase):
    def setUp(self):
        self.host = Player.objects.create(name="Host")
        self.room = Room.objects.create(room_id=12345678, host=self.host, word="Secret")
        self.host.room = self.room
        self.host.save()
        self.second = Player.objects.create(name="Second", room=self.room)
        Player.objects.create(name="Third", room=self.room)
        self.room.imposter.add(self.second)
        session = self.client.session
        session["player_id"] = self.host.pk
        session.save()

    def test_outsiders_cannot_read_roles_or_start_rounds(self):
        outsider = Client()
        self.assertEqual(outsider.get("/imposterGame/room/12345678/").status_code, 403)
        with patch("imposterGame.views.generate") as generate:
            self.assertEqual(outsider.post("/imposterGame/start-round/12345678/").status_code, 403)
            generate.assert_not_called()

    def test_non_host_cannot_start_or_kick(self):
        session = self.client.session
        session["player_id"] = self.second.pk
        session.save()
        self.assertEqual(self.client.post("/imposterGame/start-round/12345678/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/imposterGame/kick-player/12345678/", {"player_id": self.host.pk}
            ).status_code,
            403,
        )
        response = self.client.get("/imposterGame/room/12345678/")
        self.assertContains(response, "IMPOSTER")
        self.assertNotContains(response, "Secret")

    def test_state_changes_require_post_and_csrf(self):
        for url in ["create-room/", "start-round/12345678/", "leave-room/12345678/"]:
            self.assertEqual(self.client.get("/imposterGame/" + url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post("/imposterGame/create-room/").status_code, 403)

    @patch("imposterGame.views.generate", return_value="Pear")
    def test_round_persists_history_and_category(self, generate):
        UsedWord.objects.create(room=self.room, word="Apple", normalized="apple")
        response = self.client.post("/imposterGame/start-round/12345678/", {"category": "Fruit"})
        self.assertEqual(response.status_code, 302)
        generate.assert_called_once_with("word", "Fruit", ["Apple"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.word, "Pear")
        self.assertEqual(self.room.category, "Fruit")
        self.assertEqual(
            list(self.room.used_words.values_list("word", flat=True)), ["Apple", "Pear"]
        )
        self.assertEqual(self.room.imposter.count(), 1)

    def test_invalid_category_never_calls_provider(self):
        with patch("imposterGame.views.generate") as generate:
            response = self.client.post(
                "/imposterGame/start-round/12345678/", {"category": "x" * 121}
            )
            self.assertEqual(response.status_code, 400)
            generate.assert_not_called()

    def test_leaving_host_transfers_control(self):
        self.client.post("/imposterGame/leave-room/12345678/")
        self.room.refresh_from_db()
        self.assertEqual(self.room.host_id, self.second.pk)

    @patch("imposterGame.views.generate")
    def test_provider_failure_preserves_round(self, generate):
        from gameAI.service import GenerationError

        generate.side_effect = GenerationError("Service unavailable.")
        self.assertEqual(self.client.post("/imposterGame/start-round/12345678/").status_code, 503)
        self.room.refresh_from_db()
        self.assertEqual(self.room.word, "Secret")
        self.assertEqual(self.room.used_words.count(), 0)

    def test_xss_is_escaped_and_private_pages_have_security_headers(self):
        self.host.name = '<script>alert("x")</script>'
        self.host.save()
        response = self.client.get("/imposterGame/room/12345678/")
        self.assertNotContains(response, "<script>alert(")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertNotContains(response, "cdn.jsdelivr.net")


class SocketTests(TransactionTestCase):
    def communicator(self, application, session=None, origin=b"https://games.example.com"):
        return ApplicationCommunicator(
            application,
            {
                "type": "websocket",
                "path": "/ws/room/12345678/",
                "headers": [(b"origin", origin)],
                "session": session or {},
                "url_route": {"kwargs": {"room_id": 12345678}},
            },
        )

    def test_room_membership_and_client_event_rejection(self):
        player = Player.objects.create(name="Host")
        room = Room.objects.create(room_id=12345678, host=player)
        player.room = room
        player.save()

        async def run():
            outsider = self.communicator(LobbyConsumer.as_asgi())
            await outsider.send_input({"type": "websocket.connect"})
            self.assertEqual((await outsider.receive_output())["code"], 4403)
            await outsider.send_input({"type": "websocket.disconnect", "code": 1000})
            await outsider.wait()
            member = self.communicator(LobbyConsumer.as_asgi(), {"player_id": player.pk})
            await member.send_input({"type": "websocket.connect"})
            self.assertEqual((await member.receive_output())["type"], "websocket.accept")
            await member.send_input({"type": "websocket.receive", "text": '{"event":"next_round"}'})
            self.assertEqual((await member.receive_output())["code"], 4400)
            await member.send_input({"type": "websocket.disconnect", "code": 1000})
            await member.wait()

        async_to_sync(run)()

    @override_settings(ALLOWED_HOSTS=["games.example.com"], DEBUG=False)
    def test_foreign_websocket_origin_is_rejected(self):
        from mySite.asgi import application

        async def run():
            socket = self.communicator(application, origin=b"https://evil.example")
            await socket.send_input({"type": "websocket.connect"})
            self.assertEqual((await socket.receive_output())["type"], "websocket.close")
            await socket.send_input({"type": "websocket.disconnect", "code": 1000})
            await socket.wait()

        async_to_sync(run)()

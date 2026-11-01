from unittest.mock import patch

from django.test import TestCase, override_settings


@override_settings(SECURE_SSL_REDIRECT=False, AI_COOLDOWN_SECONDS=0)
class CouplesTests(TestCase):
    def test_home_and_post_only_generation(self):
        self.assertContains(self.client.get("/couplesQuestions/"), "Couples Conversations")
        self.assertEqual(self.client.get("/couplesQuestions/question/").status_code, 405)

    @patch(
        "couplesQuestions.views.generate",
        side_effect=["What makes you feel supported?", "What could we explore together?"],
    )
    def test_category_and_server_side_session_history(self, generate):
        first = self.client.post("/couplesQuestions/question/", {"category": "Future"})
        self.assertContains(first, "What makes you feel supported?")
        self.client.post("/couplesQuestions/question/", {"category": "Future"})
        generate.assert_called_with("question", "Future", ["What makes you feel supported?"])
        self.assertNotIn("What makes", self.client.cookies["sessionid"].value)
        self.client.post("/couplesQuestions/reset/")
        self.assertNotIn("couples_history", self.client.session)

    @patch("couplesQuestions.views.generate")
    def test_invalid_input_does_not_trigger_generation(self, generate):
        self.assertEqual(
            self.client.post("/couplesQuestions/question/", {"category": "x" * 121}).status_code,
            400,
        )
        generate.assert_not_called()

from django.urls import path
from . import views

app_name = "couplesQuestions"

urlpatterns = [
    path("", views.home, name="couples_home")
    path("question/", views.get_question, name="question"),
]
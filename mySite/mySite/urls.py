from django.urls import include, path

urlpatterns = [
    path("", include("home.urls")),
    path("couplesQuestions/", include("couplesQuestions.urls")),
    path("imposterGame/", include("imposterGame.urls")),
]

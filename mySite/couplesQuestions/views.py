from django.shortcuts import redirect, render

def home(request):
    return render(request, "questionnaire.html")


def get_question(request):
    #Implement logic to fetch and display a question
    return render(request, "question.html")
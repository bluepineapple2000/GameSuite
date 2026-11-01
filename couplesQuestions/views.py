from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from gameAI.forms import CategoryForm
from gameAI.service import GenerationError, generate, generation_slot


def home(request):
    return render(
        request,
        "couplesQuestions/questionnaire.html",
        {
            "form": CategoryForm(initial={"category": request.session.get("couples_category", "")}),
        },
    )


@require_POST
def get_question(request):
    form = CategoryForm(request.POST)
    question = None
    error = None
    if form.is_valid():
        try:
            with generation_slot():
                history = request.session.get("couples_history", [])
                question = generate("question", form.cleaned_data["category"], history)
                request.session["couples_history"] = [*history, question]
                request.session["couples_category"] = form.cleaned_data["category"]
        except GenerationError as exc:
            error = str(exc)
    return render(
        request,
        "couplesQuestions/question.html",
        {
            "form": form,
            "question": question,
            "error": error,
        },
        status=503 if error else (200 if form.is_valid() else 400),
    )


@require_POST
def reset(request):
    request.session.pop("couples_history", None)
    request.session.pop("couples_category", None)
    return redirect("couplesQuestions:couples_home")

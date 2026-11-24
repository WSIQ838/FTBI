"""Question rendering never sends answer keys to the learner."""
from decimal import Decimal
from django import forms


def answer_form(questions, data=None):
    form = forms.Form(data)
    for question in questions:
        key = f"q{question.pk}"
        label = f"{question.prompt} ({question.points} points)"
        if question.kind == "choice":
            form.fields[key] = forms.ChoiceField(label=label, choices=[(letter,getattr(question,"option_"+letter.lower())) for letter in "ABCD"],widget=forms.RadioSelect)
        elif question.kind == "boolean":
            form.fields[key] = forms.ChoiceField(label=label,choices=[("true","True"),("false","False")],widget=forms.RadioSelect)
        elif question.kind == "matching":
            choices = [(value,value) for value in sorted(set(question.answer_key.values()))]
            for i, prompt in enumerate(question.answer_key):
                form.fields[f"{key}_{i}"] = forms.ChoiceField(label=f"{label}: {prompt}",choices=[("","Choose a match")]+choices)
        else:
            form.fields[key] = forms.CharField(label=label,max_length=10000 if question.kind == "essay" else 500,widget=forms.Textarea if question.kind == "essay" else forms.TextInput)
    return form


def evaluate(question, data):
    key = f"q{question.pk}"
    if question.kind == "matching":
        answer = {prompt: data[f"{key}_{i}"] for i,prompt in enumerate(question.answer_key)}
        correct = sum(answer[prompt] == value for prompt,value in question.answer_key.items())
        score = (Decimal(question.points)*correct/len(answer)).quantize(Decimal("0.01"))
        return answer, score
    answer = data[key]
    if question.kind == "essay":
        return answer, None
    if question.kind == "choice":
        correct = answer == question.correct
    elif question.kind == "boolean":
        correct = (answer == "true") == question.answer_key[0]
    else:
        normalize = lambda value: " ".join(value.casefold().split())
        correct = normalize(answer) in [normalize(value) for value in question.answer_key]
    return answer, Decimal(question.points if correct else 0)


def attempt_grade(quiz, student):
    if not quiz.results_released:
        return None
    attempts = list(quiz.attempt_set.filter(student=student,graded=True).order_by("number"))
    scores = [a.score*100/a.total for a in attempts if a.total]
    if not scores:
        return None
    policy = getattr(quiz,"policy",None)
    rule = policy.attempt_rule if policy else "highest"
    result = scores[-1] if rule == "latest" else sum(scores)/len(scores) if rule == "average" else max(scores)
    return result.quantize(Decimal("0.01"))

from django import forms


class CategoryForm(forms.Form):
    category = forms.CharField(
        max_length=120,
        required=False,
        strip=True,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Travel, food, shared dreams"}),
    )

    def clean_category(self):
        value = self.cleaned_data["category"]
        if any(ord(char) < 32 for char in value):
            raise forms.ValidationError("Please enter a single line of text.")
        return value

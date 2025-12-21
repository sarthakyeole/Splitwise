from django import forms
from django.contrib.auth.models import User
from .models import Group, Expense
from django.contrib.auth.forms import UserCreationForm

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'members']
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'members': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = User.objects.order_by('username')
        self.fields['name'].help_text = "Select members to add to the group (you can include yourself)."


class ExpenseForm(forms.ModelForm):
    split_type = forms.ChoiceField(
        choices=[
            ('equal', 'Split equally'),
            ('unequal', 'Unequal split'),
        ],
        widget=forms.RadioSelect(
            attrs={'class': 'form-check-input'}
        ),
        initial='equal'
    )

    class Meta:
        model = Expense
        fields = ['description', 'amount', 'split_type']
        widgets = {
            'description': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Expense description'
                }
            ),
            'amount': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Amount'
                }
            ),
        }
        
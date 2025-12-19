from django import forms
from django.contrib.auth.models import User
from .models import Group, Expense

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'members']
        widgets = {
            'members': forms.CheckboxSelectMultiple,
        }

    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = User.objects.order_by('username')
        self.fields['name'].help_text = "select members to add to the group. (You can also add yourself)"

class ExpenseForm(forms.ModelForm):
    split_type = forms.ChoiceField(
        choices=[
            ('equal', 'split Equally'),
            ('unequal', 'Unequal Split'),
        ],
        widget=forms.RadioSelect, 
        initial='equal'
    )

    class Meta:
        model = Expense
        fields = ['description', 'amount', 'split_type']
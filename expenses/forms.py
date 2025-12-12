from django import forms
from django.contrib.auth.models import User
from .models import Group

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
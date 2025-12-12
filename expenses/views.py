from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Group, Expense, Split
from .utils import calculate_balances
from .forms import GroupForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages


@login_required
def dashboard(request):
    groups = request.user.split_groups.all()
    return render(request, 'expenses/dashboard.html', {
        'groups': groups,
    })

@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)

    balances_dict = calculate_balances(group)

    balance_entries = list(balances_dict.items())

    expenses = group.expenses.select_related('paid_by').all().order_by('-created_at')

    return render(request, 'expenses/group_detail.html', {
        'group': group,
        'balances': balance_entries,
        'expenses': expenses,
    })


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['description', 'amount']


@login_required
def add_expense(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.group = group
            expense.paid_by = request.user
            expense.save()

            # Equal split among all members
            members = group.members.all()
            share = expense.amount / members.count()

            for member in members:
                Split.objects.create(
                    expense=expense,
                    user=member,
                    amount=share,
                )

            return redirect('group_detail', group_id=group.id)
    else:
        form = ExpenseForm()

    return render(request, 'expenses/add_expense.html', {
        'group': group,
        'form': form,
    })

@login_required
def create_group(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            form.save_m2m()  
            
            if request.user not in group.members.all():
                group.members.add(request.user)

            messages.success(request, f"Group '{group.name}' created.")
            return redirect('group_detail', group_id=group.id)

    else:
        form = GroupForm()
        
    return render(request, 'expenses/create_group.html', {
        'form': form,
    })

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}. You are now logged in')

            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)

            if user is not None:
                login(request, user)

            return redirect('dashboard')

    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})
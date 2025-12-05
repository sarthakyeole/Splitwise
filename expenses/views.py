from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django import forms

from .models import Group, Expense, Split
from .utils import calculate_balance


@login_required
def dashboard(request):
    groups = request.user.groups.all()
    return render(request, 'expenses/dashboard.html', {
        'groups': groups,
    })

@login_required
def group_detail(request, group_id):
    group = get_objecct_or_404(group, id=group_id, members=request.user)
    balances = calculate_balances(group)
    expenses = group.expenses.select_related('paid_by').all().order_by('-created_at')

    return render(request, 'expenses/group_detail.html', {
        'group': group, 
        'balances': balances,
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


            members = group.members.all()
            share = expense.amount / members.count()

            for member in members:
                Split.objects.create(
                    expense=expense,
                    user=member,
                    amount=share
                )

            return redirect('group_detail', group_id=group.id)
    else:
        form = ExpenseForm()

    return render(request, 'expenses/add_expense.html', {
        'group': group,
        'form': form,
    })
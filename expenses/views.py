from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django import forms
from .models import Group, Expense, Split, Settlement, Activity
from .utils import calculate_balances, simplify_debts
from .forms import GroupForm, ExpenseForm
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

    transactions = simplify_debts(balances_dict)

    recent_activities = group.activities.order_by('-created_at')[:5]

    expenses = group.expenses.select_related('paid_by').prefetch_related('splits__user').all().order_by('-created_at')

    return render(request, 'expenses/group_detail.html', {
        'group': group,
        'balances': balance_entries,
        'transactions': transactions,
        'expenses': expenses,
        'recent_activities': recent_activities,
    })


@login_required
def add_expense(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)
    members = list(group.members.all())

    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            description = form.cleaned_data['description']
            amount = float(form.cleaned_data['amount'])
            split_type = form.cleaned_data.get('split_type', 'equal')

            # create expense first
            expense = Expense.objects.create(
                group=group,
                description=description,
                amount=amount,
                paid_by=request.user
            )

            # Equal split
            if split_type == 'equal':
                per_share = round(amount / len(members), 2)
                # adjust last person's share to match total (to avoid tiny rounding diff)
                for i, m in enumerate(members):
                    share = per_share
                    if i == len(members) - 1:
                        share = round(amount - per_share * (len(members) - 1), 2)
                    Split.objects.create(expense=expense, user=m, amount=share)
                    
                # Activity log for the equal split expense
                Activity.objects.create(
                    group=group,
                    user=request.user,
                    message=f'{request.user.username} added expense "{expense.description}" ₹{expense.amount}'
                )

                messages.success(request, "Expense saved (equal split).")
                return redirect('group_detail', group_id=group.id)

            # Unequal split
            else:
                splits_to_create = []
                total_share = 0.0
                # read each member's share from POST: share_<user_id>
                for m in members:
                    key = f"share_{m.id}"
                    raw = request.POST.get(key, '').strip()
                    try:
                        share_value = float(raw) if raw != '' else 0.0
                    except ValueError:
                        expense.delete()
                        return render(request, 'expenses/add_expense.html', {
                            'group': group, 'form': form, 'members': members,
                            'error': f"Invalid number for {m.username}: {raw}"
                        })
                    total_share += share_value
                    splits_to_create.append((m, round(share_value, 2)))

                # validate total equals expense amount within tolerance
                if abs(total_share - amount) > 0.01:
                    expense.delete()
                    return render(request, 'expenses/add_expense.html', {
                        'group': group, 'form': form, 'members': members,
                        'error': f"Total shares ({total_share}) must equal expense amount ({amount})."
                    })

                # create Split objects
                for m, share in splits_to_create:
                    Split.objects.create(expense=expense, user=m, amount=share)

                # Activity log for the unequal split expense
                Activity.objects.create(
                    group=group,
                    user=request.user,
                    message=f'{request.user.username} added expense "{expense.description}" ₹{expense.amount}'
                )

                messages.success(request, "Expense saved (unequal split).")
                return redirect('group_detail', group_id=group.id)

        return render(request, 'expenses/add_expense.html', {
            'group': group, 'form': form, 'members': members,
        })

    else:
        form = ExpenseForm()
        
    return render(request, 'expenses/add_expense.html', {
        'group': group, 
        'form': form, 
        'members': members,
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

@login_required
def quick_settle(request, group_id):
    if request.method == 'POST':
        group = get_object_or_404(Group, id=group_id, members=request.user)

        paid_by_id = int(request.POST['paid_by'])
        paid_to_id = int(request.POST['paid_to'])
        amount = float(request.POST['amount'])

        balances = calculate_balances(group)

        debtor = User.objects.get(id=paid_by_id)
        creditor = User.objects.get(id=paid_to_id)

        debtor_balance = balances.get(debtor, 0)
        owed_amount = abs(debtor_balance)

        if amount <= 0 or amount > owed_amount:
            return redirect('group_detail', group_id=group_id)

        Settlement.objects.create(
            group=group,
            paid_by=debtor,
            paid_to=creditor,
            amount=amount
        )

        # New Activity log
        Activity.objects.create(
            group=group,
            user=request.user,
            message=f'{debtor.username} settled ₹{amount} with {creditor.username}'
        )

    return redirect('group_detail', group_id=group_id)

@login_required
def activity_log(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)

    activities = group.activities.order_by('-created_at')

    return render(request, 'expenses/activity_log.html', {
        'group': group, 
        'activities': activities,
    })

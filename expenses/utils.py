from collections import defaultdict
from .models import Group 

def calculate_balances(group: Group):
    """
    Returns a dict: {user: net_amount}
    +ve => others owe this user
    -ve => this user owes others
    """

    balances = defaultdict(float)

    # 1) apply expenses and splits
    for expense in group.expenses.select_related('paid_by').prefetch_related('splits__user'):
        # paid_by gets +total amount
        balances[expense.paid_by] += float(expense.amount)

        # each user owes their split amount 
        for split in expense.splits.all():
            balances[split.user] -= float(split.amount)

    
    # 2) apply settlements (who paid to whom back)
    # for s in group.settlements.select_related('paid_by', 'paid_to'):
    #     balances[s.paid_by] -= float(s.amount)
    #     balances[s.paid_to] += float(s.amount)


    return balances
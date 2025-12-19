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


def simplify_debts(balances):
    """
    Input: balances dictionary {user: amount}
    Output: list of (from_user, to_user, amount)
    """

    creditors = []      # people who should receive money (as they already paid)
    debtors = []        # people who owes money (they have to pay to others)

    for user, amount in balances.items():
        if amount > 0:
            creditors.append([user, amount])
        elif amount < 0:
            debtors.append([user, -amount])

    i = j = 0
    transactions = []

    while i < len(debtors) and j < len(creditors):
        debtor, debt_amount = debtors[i]
        creditor, credit_amount = creditors[j]

        settle_amount = min(debt_amount, credit_amount)

        transactions.append((debtor, creditor, round(settle_amount, 2)))

        debtors[i][1] -= settle_amount
        creditors[j][1] -= settle_amount

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return transactions
from django.db import models
from django.contrib.auth.models import User

class Group(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_groups'
    )

    members = models.ManyToManyField(
        User,
        related_name='split_groups'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Expense(models.Model):
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE,
        related_name='expenses'
    )

    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='paid_expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"


class Split(models.Model):
    expense = models.ForeignKey(
        Expense, 
        on_delete=models.CASCADE,
        related_name='splits'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='splits'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} owes {self.amount} for {self.expense.description}"


class Settlement(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('CREATED', 'Created'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='settlements'
    )

    paid_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='settlements_made'
    )

    paid_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='settlements_received'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    razorpay_order_id = models.CharField(
        max_length=100, blank=True, null=True
    )
    razorpay_payment_id = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )
    razorpay_signature = models.CharField(
        max_length=100, blank=True, null=True
    )

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='CREATED'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.paid_by.username} paid {self.paid_to.username}"
            f"₹{self.amount} [{self.status}]"
        )


class Activity(models.Model):
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        related_name='activities'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message

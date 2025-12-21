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
import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

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

@login_required
def export_group_csv(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{group.name}_summary.csv"'

    writer = csv.writer(response)

    # Group info
    writer.writerow(['Group Name', group.name])
    writer.writerow([])
    
    # Members
    writer.writerow(['Members'])
    for m in group.members.all():
        writer.writerow([m.username])
    writer.writerow([])

    # Expenses
    writer.writerow(['Expenses'])
    writer.writerow(['Description', 'Paid By', 'Amount'])
    for e in group.expenses.select_related('paid_by'):
        writer.writerow([e.description, e.paid_by.username, e.amount])
    writer.writerow([])

    # Settlements
    writer.writerow(['Settlements'])
    writer.writerow(['Paid By', 'Paid To', 'Amount'])
    for s in group.settlements.select_related('paid_by', 'paid_to'):
        writer.writerow([s.paid_by.username, s.paid_to.username, s.amount])
    writer.writerow([])

    # Final balances
    balances = calculate_balances(group)
    writer.writerow(['Final Balances'])
    writer.writerow(['User', 'Net Amount'])
    for user, amount in balances.items():
        writer.writerow([user.username, amount])

    return response

@login_required
def export_group_pdf(request, group_id):
    group = get_object_or_404(Group, id=group_id, members=request.user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{group.name}_summary.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    # Starting position
    y = height - 2 * cm
    left_margin = 2 * cm
    right_margin = width - 2 * cm

    def draw_header():
        """Draw the header section with title and date"""
        nonlocal y
        
        # Title with background
        p.setFillColorRGB(0.2, 0.4, 0.8)  # Blue background
        p.rect(left_margin - 0.3*cm, y - 0.9*cm, right_margin - left_margin + 0.6*cm, 1.3*cm, fill=1, stroke=0)
        
        # White text on blue background
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(left_margin + 0.2*cm, y - 0.45*cm, f"Group Summary: {group.name}")
        
        # Date on the right
        p.setFont("Helvetica", 10)
        date_str = datetime.now().strftime("%B %d, %Y")
        p.drawRightString(right_margin - 0.2*cm, y - 0.45*cm, f"Generated: {date_str}")
        
        y -= 2.8 * cm
        p.setFillColorRGB(0, 0, 0)  # Reset to black

    def draw_section_header(title):
        """Draw a section header with underline"""
        nonlocal y
        if y < 6 * cm:  # Check if we need a new page (more conservative)
            p.showPage()
            y = height - 2 * cm
        
        # Add spacing before section
        y -= 0.5 * cm
        
        p.setFont("Helvetica-Bold", 14)
        p.setFillColorRGB(0.2, 0.4, 0.8)
        p.drawString(left_margin, y, title)
        
        # Draw underline
        p.setStrokeColorRGB(0.2, 0.4, 0.8)
        p.setLineWidth(2)
        p.line(left_margin, y - 0.15*cm, right_margin, y - 0.15*cm)
        
        y -= 0.9 * cm  # Spacing after header
        p.setFillColorRGB(0, 0, 0)
        p.setStrokeColorRGB(0, 0, 0)
        p.setLineWidth(1)

    def draw_text(text, indent=0, bold=False):
        """Draw regular text with optional indent"""
        nonlocal y
        if y < 2 * cm:
            p.showPage()
            y = height - 2 * cm
        
        if bold:
            p.setFont("Helvetica-Bold", 11)
        else:
            p.setFont("Helvetica", 11)
        
        p.drawString(left_margin + indent * cm, y, text)
        y -= 0.6 * cm

    def draw_table(data, col_widths=None):
        """Draw a formatted table"""
        nonlocal y
        
        if not data:
            return
        
        # Default column widths if not specified
        if col_widths is None:
            col_widths = [width / len(data[0]) - 0.5*cm for _ in data[0]]
        
        # Calculate approximate table height (more accurate)
        row_height = 0.75 * cm
        table_height = len(data) * row_height + 0.5 * cm
        
        # Check if we need a new page
        if y - table_height < 3.5 * cm:
            p.showPage()
            y = height - 2 * cm
        
        # Create table
        table = Table(data, colWidths=col_widths, rowHeights=row_height)
        
        # Style the table
        style = TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3366CC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#3366CC')),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ])
        
        table.setStyle(style)
        
        # Calculate actual table size
        table_width, actual_height = table.wrap(width - 4*cm, height)
        
        # Draw the table
        table.drawOn(p, left_margin, y - actual_height)
        
        # Update y position with actual height plus spacing
        y -= actual_height + 1.5 * cm

    # Start drawing the PDF
    draw_header()
    
    # Members Section
    draw_section_header("Group Members")
    members_data = [['Username']]
    for m in group.members.all():
        members_data.append([m.username])
    draw_table(members_data, col_widths=[10*cm])
    
    # Expenses Section
    draw_section_header("Expenses")
    expenses = group.expenses.select_related('paid_by').order_by('-created_at')
    if expenses.exists():
        expenses_data = [['Description', 'Paid By', 'Amount (₹)']]
        for e in expenses:
            expenses_data.append([
                e.description[:40],  # Truncate long descriptions
                e.paid_by.username,
                f"₹{e.amount:.2f}"
            ])
        draw_table(expenses_data, col_widths=[9*cm, 4*cm, 4*cm])
    else:
        draw_text("No expenses recorded yet.", indent=0.5)
        y -= 0.5 * cm
    
    # Settlements Section
    draw_section_header("Settlements")
    settlements = group.settlements.select_related('paid_by', 'paid_to').order_by('-created_at')
    if settlements.exists():
        settlements_data = [['Paid By', 'Paid To', 'Amount (₹)']]
        for s in settlements:
            settlements_data.append([
                s.paid_by.username,
                s.paid_to.username,
                f"₹{s.amount:.2f}"
            ])
        draw_table(settlements_data, col_widths=[5*cm, 5*cm, 4*cm])
    else:
        draw_text("No settlements recorded yet.", indent=0.5)
        y -= 0.5 * cm
    
    # Final Balances Section
    draw_section_header("Final Balances")
    balances = calculate_balances(group)
    if balances:
        balances_data = [['Member', 'Balance (₹)', 'Status']]
        for user, amount in sorted(balances.items(), key=lambda x: x[1], reverse=True):
            status = "Should Receive" if amount > 0 else "Owes" if amount < 0 else "Settled"
            balances_data.append([
                user.username,
                f"₹{abs(amount):.2f}",
                status
            ])
        draw_table(balances_data, col_widths=[6*cm, 4*cm, 5*cm])
    else:
        draw_text("No balance information available.", indent=0.5)
        y -= 0.5 * cm
    
    # Who Should Pay Whom Section
    draw_section_header("Settlement Recommendations")
    transactions = simplify_debts(balances)
    if transactions:
        transactions_data = [['From', 'To', 'Amount (₹)']]
        for debtor, creditor, amount in transactions:
            transactions_data.append([
                debtor.username,
                creditor.username,
                f"₹{amount:.2f}"
            ])
        draw_table(transactions_data, col_widths=[5*cm, 5*cm, 4*cm])
    else:
        draw_text("✓ All settled! No pending payments.", indent=0.5, bold=True)
    
    # Footer
    y = 1.5 * cm
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawCentredString(width / 2, y, f"Generated by Splitwise - {group.name}")
    
    p.showPage()
    p.save()

    return response
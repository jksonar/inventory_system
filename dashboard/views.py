from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv

from inventory.models import Product, InventoryTransaction
from sales.models import Sale, SaleItem
from .models import Alert, ActivityLog

@login_required
def dashboard_home(request):
    """Dashboard home view with summary statistics and alerts"""
    # Get current date and date range for statistics
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    # Inventory statistics
    total_products = Product.objects.count()
    low_stock_products = Product.objects.filter(quantity_in_stock__lte=F('reorder_level')).count()
    out_of_stock_products = Product.objects.filter(quantity_in_stock=0).count()
    
    # Sales statistics
    today_sales = Sale.objects.filter(sale_date__date=today).aggregate(
        total=Sum('final_amount', default=0),
        count=Count('id')
    )
    
    week_sales = Sale.objects.filter(sale_date__date__gte=start_of_week).aggregate(
        total=Sum('final_amount', default=0),
        count=Count('id')
    )
    
    month_sales = Sale.objects.filter(sale_date__date__gte=start_of_month).aggregate(
        total=Sum('final_amount', default=0),
        count=Count('id')
    )
    
    # Recent sales
    recent_sales = Sale.objects.order_by('-sale_date')[:5]
    
    # Recent inventory transactions
    recent_transactions = InventoryTransaction.objects.order_by('-transaction_date')[:5]
    
    # Alerts for current user
    alerts = Alert.objects.filter(
        Q(target_users=request.user) | Q(target_users__isnull=True),
        is_read=False
    ).order_by('-priority', '-created_at')[:10]
    
    # Top selling products
    top_products = SaleItem.objects.values(
        'product__name', 'product__id'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum('total_price')
    ).order_by('-total_quantity')[:5]
    
    context = {
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'today_sales': today_sales,
        'week_sales': week_sales,
        'month_sales': month_sales,
        'recent_sales': recent_sales,
        'recent_transactions': recent_transactions,
        'alerts': alerts,
        'top_products': top_products,
    }
    
    return render(request, 'dashboard/home.html', context)

@login_required
def alerts_list(request):
    """View for listing all alerts"""
    alerts = Alert.objects.filter(
        Q(target_users=request.user) | Q(target_users__isnull=True)
    ).order_by('-created_at')
    
    return render(request, 'dashboard/alerts.html', {'alerts': alerts})

@login_required
def activity_logs(request):
    """View for listing activity logs"""
    # Admin can see all logs, others can only see their own
    if request.user.user_type == 'admin':
        logs = ActivityLog.objects.all().order_by('-timestamp')
    else:
        logs = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')
    
    return render(request, 'dashboard/activity_logs.html', {'logs': logs})

@login_required
def export_logs(request):
    """Export activity logs as CSV"""
    # Admin can export all logs, others can only export their own
    if request.user.user_type == 'admin':
        logs = ActivityLog.objects.all().order_by('-timestamp')
    else:
        logs = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="activity_logs.csv"'
    
    # Create CSV writer and write header row
    writer = csv.writer(response)
    writer.writerow(['User', 'Action', 'Entity Type', 'Entity ID', 'Description', 'IP Address', 'Timestamp'])
    
    # Write data rows
    for log in logs:
        writer.writerow([
            log.user.username,
            log.get_action_display() if hasattr(log, 'get_action_display') else log.action,
            log.entity_type,
            log.entity_id,
            log.description,
            log.ip_address,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Log this export activity
    ActivityLog.objects.create(
        user=request.user,
        action='export',
        entity_type='activity_logs',
        description=f'Exported activity logs',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

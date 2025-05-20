from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.template.loader import get_template
from django.conf import settings

import os
import csv
import tempfile
from datetime import datetime, timedelta
from xhtml2pdf import pisa
import xlsxwriter
from io import BytesIO

from .models import Report
from inventory.models import Product, InventoryTransaction, Category
from sales.models import Sale, SaleItem
from dashboard.models import ActivityLog

@login_required
def reports_home(request):
    """Home view for reports section"""
    # Get recent reports
    recent_reports = Report.objects.filter(generated_by=request.user).order_by('-generated_at')[:5]
    
    context = {
        'recent_reports': recent_reports,
    }
    
    return render(request, 'reports/reports_home.html', context)

@login_required
@permission_required('reports.add_report', raise_exception=True)
def sales_report(request):
    """Generate sales report based on date range"""
    # Default date range (last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get date range from request
    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        report_format = request.POST.get('report_format', 'html')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Add one day to end_date to include the end date in the range
        end_date_query = end_date + timedelta(days=1)
        
        # Get sales data
        sales = Sale.objects.filter(
            sale_date__date__gte=start_date,
            sale_date__date__lt=end_date_query
        ).order_by('-sale_date')
        
        # Calculate summary statistics
        summary = sales.aggregate(
            total_sales=Sum('final_amount', default=0),
            total_items=Count('items'),
            total_transactions=Count('id')
        )
        
        # Get daily sales totals
        daily_sales = sales.values('sale_date__date').annotate(
            daily_total=Sum('final_amount'),
            transactions=Count('id')
        ).order_by('sale_date__date')
        
        # Get top selling products
        top_products = SaleItem.objects.filter(
            sale__sale_date__date__gte=start_date,
            sale__sale_date__date__lt=end_date_query
        ).values(
            'product__name', 'product__sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_sales=Sum('total_price')
        ).order_by('-total_quantity')[:10]
        
        # Get payment method breakdown
        payment_methods = sales.values('payment_method').annotate(
            total=Sum('final_amount'),
            count=Count('id')
        ).order_by('-total')
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'sales': sales,
            'summary': summary,
            'daily_sales': daily_sales,
            'top_products': top_products,
            'payment_methods': payment_methods,
        }
        
        # Generate report in requested format
        if report_format == 'pdf':
            return generate_pdf_report(
                request, 
                'reports/sales_report_pdf.html', 
                context, 
                f"Sales Report {start_date} to {end_date}"
            )
        elif report_format == 'excel':
            return generate_excel_report(
                request,
                sales,
                top_products,
                daily_sales,
                f"Sales Report {start_date} to {end_date}"
            )
        elif report_format == 'csv':
            return generate_csv_report(
                request,
                sales,
                f"Sales Report {start_date} to {end_date}"
            )
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'reports/sales_report_form.html', context)

@login_required
@permission_required('reports.add_report', raise_exception=True)
def inventory_report(request):
    """Generate inventory status report"""
    # Get filter parameters
    category_id = request.GET.get('category')
    supplier_id = request.GET.get('supplier')
    stock_status = request.GET.get('stock_status')
    report_format = request.GET.get('report_format', 'html')
    
    # Base queryset
    products = Product.objects.all().order_by('category__name', 'name')
    
    # Apply filters
    if category_id:
        products = products.filter(category_id=category_id)
    
    if supplier_id:
        products = products.filter(supplier_id=supplier_id)
    
    if stock_status == 'low':
        products = products.filter(quantity_in_stock__lte=F('reorder_level'))
    elif stock_status == 'out':
        products = products.filter(quantity_in_stock=0)
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    # Calculate summary statistics
    summary = {
        'total_products': products.count(),
        'total_value': products.aggregate(value=Sum(F('quantity_in_stock') * F('unit_price'), default=0))['value'],
        'low_stock': products.filter(quantity_in_stock__lte=F('reorder_level')).count(),
        'out_of_stock': products.filter(quantity_in_stock=0).count(),
    }
    
    context = {
        'products': products,
        'categories': categories,
        'summary': summary,
        'selected_category': category_id,
        'selected_supplier': supplier_id,
        'selected_stock_status': stock_status,
    }
    
    # Generate report in requested format
    if report_format == 'pdf':
        return generate_pdf_report(
            request, 
            'reports/inventory_report_pdf.html', 
            context, 
            "Inventory Status Report"
        )
    elif report_format == 'excel':
        return generate_excel_inventory_report(
            request,
            products,
            "Inventory Status Report"
        )
    elif report_format == 'csv':
        return generate_csv_inventory_report(
            request,
            products,
            "Inventory Status Report"
        )
    
    return render(request, 'reports/inventory_report.html', context)

@login_required
@permission_required('reports.add_report', raise_exception=True)
def low_stock_report(request):
    """Generate low stock report"""
    # Get products with low stock
    products = Product.objects.filter(
        quantity_in_stock__lte=F('reorder_level')
    ).order_by('quantity_in_stock', 'name')
    
    report_format = request.GET.get('report_format', 'html')
    
    # Calculate summary statistics
    summary = {
        'total_low_stock': products.count(),
        'out_of_stock': products.filter(quantity_in_stock=0).count(),
        'total_reorder_value': products.aggregate(
            value=Sum(F('reorder_quantity') * F('unit_price'), default=0)
        )['value'],
    }
    
    context = {
        'products': products,
        'summary': summary,
    }
    
    # Generate report in requested format
    if report_format == 'pdf':
        return generate_pdf_report(
            request, 
            'reports/low_stock_report_pdf.html', 
            context, 
            "Low Stock Report"
        )
    elif report_format == 'excel':
        return generate_excel_low_stock_report(
            request,
            products,
            "Low Stock Report"
        )
    
    return render(request, 'reports/low_stock_report.html', context)

@login_required
@permission_required('reports.add_report', raise_exception=True)
def custom_report(request):
    """Generate custom report based on user parameters"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        category_id = request.POST.get('category')
        report_format = request.POST.get('report_format', 'html')
        
        # Redirect to appropriate report with parameters
        if report_type == 'sales':
            return redirect(f'/reports/sales/?start_date={start_date}&end_date={end_date}&report_format={report_format}')
        elif report_type == 'inventory':
            return redirect(f'/reports/inventory/?category={category_id}&report_format={report_format}')
        elif report_type == 'low_stock':
            return redirect(f'/reports/low-stock/?report_format={report_format}')
    
    # Get categories for filter dropdown
    categories = Category.objects.all()
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'reports/custom_report_form.html', context)

@login_required
def download_report(request, pk):
    """Download a previously generated report"""
    report = get_object_or_404(Report, pk=pk)
    
    # Check if user has permission to download this report
    if report.generated_by != request.user and not request.user.is_staff:
        return HttpResponse("You don't have permission to download this report", status=403)
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='download',
        entity_type='report',
        entity_id=report.id,
        description=f"Downloaded {report.report_type} report: {report.title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Serve the file
    response = FileResponse(open(report.file_path.path, 'rb'))
    return response

# Helper functions for report generation
def generate_pdf_report(request, template_path, context, title):
    """Generate PDF report from template"""
    template = get_template(template_path)
    html = template.render(context)
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.pdf"'
    
    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    
    # Save report record
    report_file = BytesIO()
    pisa.CreatePDF(html, dest=report_file)
    report_file.seek(0)
    
    # Create report record
    report_type = 'sales' if 'Sales' in title else 'inventory' if 'Inventory' in title else 'low_stock'
    report = Report.objects.create(
        title=title,
        report_type=report_type,
        parameters=context.get('summary', {}),
        generated_by=request.user
    )
    
    # Save file to report record
    report.file_path.save(
        f"{report_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        BytesIO(report_file.getvalue())
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated {report_type} report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

def generate_excel_report(request, sales, top_products, daily_sales, title):
    """Generate Excel sales report"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # Add sales worksheet
    sales_worksheet = workbook.add_worksheet("Sales")
    
    # Add headers
    headers = ['Invoice #', 'Date', 'Customer', 'Items', 'Total', 'Discount', 'Tax', 'Final Amount', 'Payment Method', 'Status']
    for col, header in enumerate(headers):
        sales_worksheet.write(0, col, header)
    
    # Add sales data
    for row, sale in enumerate(sales, start=1):
        sales_worksheet.write(row, 0, sale.invoice_number)
        sales_worksheet.write(row, 1, sale.sale_date.strftime('%Y-%m-%d %H:%M'))
        sales_worksheet.write(row, 2, sale.customer_name or 'Walk-in')
        sales_worksheet.write(row, 3, sale.items.count())
        sales_worksheet.write(row, 4, float(sale.total_amount))
        sales_worksheet.write(row, 5, float(sale.discount))
        sales_worksheet.write(row, 6, float(sale.tax))
        sales_worksheet.write(row, 7, float(sale.final_amount))
        sales_worksheet.write(row, 8, sale.payment_method)
        sales_worksheet.write(row, 9, sale.payment_status)
    
    # Add top products worksheet
    products_worksheet = workbook.add_worksheet("Top Products")
    
    # Add headers
    headers = ['Product', 'SKU', 'Quantity Sold', 'Total Sales']
    for col, header in enumerate(headers):
        products_worksheet.write(0, col, header)
    
    # Add top products data
    for row, product in enumerate(top_products, start=1):
        products_worksheet.write(row, 0, product['product__name'])
        products_worksheet.write(row, 1, product['product__sku'])
        products_worksheet.write(row, 2, product['total_quantity'])
        products_worksheet.write(row, 3, float(product['total_sales']))
    
    # Add daily sales worksheet
    daily_worksheet = workbook.add_worksheet("Daily Sales")
    
    # Add headers
    headers = ['Date', 'Total Sales', 'Transactions']
    for col, header in enumerate(headers):
        daily_worksheet.write(0, col, header)
    
    # Add daily sales data
    for row, day in enumerate(daily_sales, start=1):
        daily_worksheet.write(row, 0, day['sale_date__date'].strftime('%Y-%m-%d'))
        daily_worksheet.write(row, 1, float(day['daily_total']))
        daily_worksheet.write(row, 2, day['transactions'])
    
    workbook.close()
    output.seek(0)
    
    # Create response
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.xlsx"'
    
    # Create report record
    report = Report.objects.create(
        title=title,
        report_type='sales',
        parameters={'format': 'excel'},
        generated_by=request.user
    )
    
    # Save file to report record
    output.seek(0)
    report.file_path.save(
        f"sales_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        BytesIO(output.getvalue())
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated Excel sales report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

def generate_csv_report(request, sales, title):
    """Generate CSV sales report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Date', 'Customer', 'Items', 'Total', 'Discount', 'Tax', 'Final Amount', 'Payment Method', 'Status'])
    
    for sale in sales:
        writer.writerow([
            sale.invoice_number,
            sale.sale_date.strftime('%Y-%m-%d %H:%M'),
            sale.customer_name or 'Walk-in',
            sale.items.count(),
            float(sale.total_amount),
            float(sale.discount),
            float(sale.tax),
            float(sale.final_amount),
            sale.payment_method,
            sale.payment_status
        ])
    
    # Create report record
    report = Report.objects.create(
        title=title,
        report_type='sales',
        parameters={'format': 'csv'},
        generated_by=request.user
    )
    
    # Save file to report record
    report.file_path.save(
        f"sales_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv",
        BytesIO(response.content)
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated CSV sales report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

def generate_excel_inventory_report(request, products, title):
    """Generate Excel inventory report"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Inventory")
    
    # Add headers
    headers = ['SKU', 'Product Name', 'Category', 'Supplier', 'Quantity', 'Unit Price', 'Value', 'Reorder Level', 'Status']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # Add product data
    for row, product in enumerate(products, start=1):
        status = 'Out of Stock' if product.quantity_in_stock == 0 else 'Low Stock' if product.quantity_in_stock <= product.reorder_level else 'In Stock'
        
        worksheet.write(row, 0, product.sku)
        worksheet.write(row, 1, product.name)
        worksheet.write(row, 2, product.category.name if product.category else 'N/A')
        worksheet.write(row, 3, product.supplier.name if product.supplier else 'N/A')
        worksheet.write(row, 4, product.quantity_in_stock)
        worksheet.write(row, 5, float(product.unit_price))
        worksheet.write(row, 6, float(product.quantity_in_stock * product.unit_price))
        worksheet.write(row, 7, product.reorder_level)
        worksheet.write(row, 8, status)
    
    workbook.close()
    output.seek(0)
    
    # Create response
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.xlsx"'
    
    # Create report record
    report = Report.objects.create(
        title=title,
        report_type='inventory',
        parameters={'format': 'excel'},
        generated_by=request.user
    )
    
    # Save file to report record
    output.seek(0)
    report.file_path.save(
        f"inventory_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        BytesIO(output.getvalue())
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated Excel inventory report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

def generate_csv_inventory_report(request, products, title):
    """Generate CSV inventory report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Product Name', 'Category', 'Supplier', 'Quantity', 'Unit Price', 'Value', 'Reorder Level', 'Status'])
    
    for product in products:
        status = 'Out of Stock' if product.quantity_in_stock == 0 else 'Low Stock' if product.quantity_in_stock <= product.reorder_level else 'In Stock'
        
        writer.writerow([
            product.sku,
            product.name,
            product.category.name if product.category else 'N/A',
            product.supplier.name if product.supplier else 'N/A',
            product.quantity_in_stock,
            float(product.unit_price),
            float(product.quantity_in_stock * product.unit_price),
            product.reorder_level,
            status
        ])
    
    # Create report record
    report = Report.objects.create(
        title=title,
        report_type='inventory',
        parameters={'format': 'csv'},
        generated_by=request.user
    )
    
    # Save file to report record
    report.file_path.save(
        f"inventory_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv",
        BytesIO(response.content)
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated CSV inventory report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

def generate_excel_low_stock_report(request, products, title):
    """Generate Excel low stock report"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Low Stock")
    
    # Add headers
    headers = ['SKU', 'Product Name', 'Current Stock', 'Reorder Level', 'Reorder Quantity', 'Unit Price', 'Reorder Value']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # Add product data
    for row, product in enumerate(products, start=1):
        worksheet.write(row, 0, product.sku)
        worksheet.write(row, 1, product.name)
        worksheet.write(row, 2, product.quantity_in_stock)
        worksheet.write(row, 3, product.reorder_level)
        worksheet.write(row, 4, product.reorder_quantity)
        worksheet.write(row, 5, float(product.unit_price))
        worksheet.write(row, 6, float(product.reorder_quantity * product.unit_price))
    
    workbook.close()
    output.seek(0)
    
    # Create response
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.xlsx"'
    
    # Create report record
    report = Report.objects.create(
        title=title,
        report_type='low_stock',
        parameters={'format': 'excel'},
        generated_by=request.user
    )
    
    # Save file to report record
    output.seek(0)
    report.file_path.save(
        f"low_stock_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        BytesIO(output.getvalue())
    )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='generate',
        entity_type='report',
        entity_id=report.id,
        description=f"Generated Excel low stock report: {title}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

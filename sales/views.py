from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction
from django.template.loader import get_template
from django.conf import settings

from .models import Sale, SaleItem
from .forms import SaleForm, SaleItemFormSet
from inventory.models import Product
from dashboard.models import ActivityLog

import os
from datetime import datetime
from xhtml2pdf import pisa

@login_required
def sales_list(request):
    """View for listing all sales"""
    sales = Sale.objects.all().order_by('-sale_date')
    return render(request, 'sales/sales_list.html', {'sales': sales})

@login_required
@permission_required('sales.add_sale', raise_exception=True)
def sale_add(request):
    """View for adding a new sale"""
    if request.method == 'POST':
        form = SaleForm(request.POST)
        formset = SaleItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Generate invoice number
                    today = timezone.now().date()
                    invoice_prefix = f"INV-{today.strftime('%Y%m%d')}"
                    last_invoice = Sale.objects.filter(
                        invoice_number__startswith=invoice_prefix
                    ).order_by('-invoice_number').first()
                    
                    if last_invoice:
                        last_num = int(last_invoice.invoice_number.split('-')[-1])
                        invoice_num = f"{invoice_prefix}-{last_num + 1:04d}"
                    else:
                        invoice_num = f"{invoice_prefix}-0001"
                    
                    # Create sale
                    sale = form.save(commit=False)
                    sale.invoice_number = invoice_num
                    sale.created_by = request.user
                    
                    # Calculate totals
                    total_amount = 0
                    for form in formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            product = form.cleaned_data.get('product')
                            quantity = form.cleaned_data.get('quantity')
                            unit_price = form.cleaned_data.get('unit_price')
                            
                            # Check if enough stock is available
                            if product.quantity_in_stock < quantity:
                                raise ValueError(f"Not enough stock for {product.name}. Available: {product.quantity_in_stock}")
                            
                            total_amount += quantity * unit_price
                    
                    sale.total_amount = total_amount
                    sale.final_amount = total_amount - sale.discount + sale.tax
                    sale.save()
                    
                    # Save sale items
                    sale_items = formset.save(commit=False)
                    for sale_item in sale_items:
                        if not sale_item.DELETE:
                            sale_item.sale = sale
                            sale_item.total_price = sale_item.quantity * sale_item.unit_price
                            sale_item.save()
                    
                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        action='create',
                        entity_type='sale',
                        entity_id=sale.id,
                        description=f"Created sale with invoice #{sale.invoice_number}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Sale recorded successfully with invoice #{sale.invoice_number}")
                    return redirect('sales:sale_detail', pk=sale.id)
            
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error recording sale: {str(e)}")
    else:
        form = SaleForm()
        formset = SaleItemFormSet()
    
    # Get products for dynamic form
    products = Product.objects.filter(quantity_in_stock__gt=0).values('id', 'name', 'sku', 'unit_price', 'quantity_in_stock')
    
    return render(request, 'sales/sale_form.html', {
        'form': form,
        'formset': formset,
        'products': products,
    })

@login_required
def sale_detail(request, pk):
    """View for displaying sale details"""
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/sale_detail.html', {'sale': sale})

@login_required
@permission_required('sales.change_sale', raise_exception=True)
def sale_edit(request, pk):
    """View for editing a sale"""
    sale = get_object_or_404(Sale, pk=pk)
    
    # Only allow editing sales that are not too old (e.g., within 24 hours)
    time_threshold = timezone.now() - timezone.timedelta(hours=24)
    if sale.created_at < time_threshold:
        messages.error(request, "Cannot edit sales older than 24 hours")
        return redirect('sales:sale_detail', pk=sale.id)
    
    if request.method == 'POST':
        form = SaleForm(request.POST, instance=sale)
        formset = SaleItemFormSet(request.POST, instance=sale)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save the sale form
                    sale = form.save(commit=False)
                    
                    # Calculate totals
                    total_amount = 0
                    for form in formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            product = form.cleaned_data.get('product')
                            quantity = form.cleaned_data.get('quantity')
                            unit_price = form.cleaned_data.get('unit_price')
                            
                            # For existing items, check if quantity increased
                            if form.instance.pk:
                                old_quantity = SaleItem.objects.get(pk=form.instance.pk).quantity
                                quantity_diff = quantity - old_quantity
                                
                                if quantity_diff > 0 and product.quantity_in_stock < quantity_diff:
                                    raise ValueError(f"Not enough stock for {product.name}. Available: {product.quantity_in_stock}")
                            else:
                                # New item, check full quantity
                                if product.quantity_in_stock < quantity:
                                    raise ValueError(f"Not enough stock for {product.name}. Available: {product.quantity_in_stock}")
                            
                            total_amount += quantity * unit_price
                    
                    sale.total_amount = total_amount
                    sale.final_amount = total_amount - sale.discount + sale.tax
                    sale.save()
                    
                    # Save sale items
                    formset.save()
                    
                    # Update product quantities
                    for form in formset:
                        if form.cleaned_data:
                            if form.cleaned_data.get('DELETE', False):
                                # If item is deleted, return stock
                                if form.instance.pk:
                                    product = form.instance.product
                                    product.quantity_in_stock += form.instance.quantity
                                    product.save()
                            elif form.instance.pk:
                                # Existing item, adjust stock based on quantity change
                                product = form.cleaned_data.get('product')
                                old_quantity = SaleItem.objects.get(pk=form.instance.pk).quantity
                                new_quantity = form.cleaned_data.get('quantity')
                                quantity_diff = new_quantity - old_quantity
                                
                                if quantity_diff != 0:
                                    product.quantity_in_stock -= quantity_diff
                                    product.save()
                            else:
                                # New item, deduct stock
                                product = form.cleaned_data.get('product')
                                quantity = form.cleaned_data.get('quantity')
                                product.quantity_in_stock -= quantity
                                product.save()
                    
                    # Log activity
                    ActivityLog.objects.create(
                        user=request.user,
                        action='update',
                        entity_type='sale',
                        entity_id=sale.id,
                        description=f"Updated sale with invoice #{sale.invoice_number}",
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.success(request, f"Sale updated successfully with invoice #{sale.invoice_number}")
                    return redirect('sales:sale_detail', pk=sale.id)
            
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error updating sale: {str(e)}")
    else:
        form = SaleForm(instance=sale)
        formset = SaleItemFormSet(instance=sale)
    
    # Get products for dynamic form
    products = Product.objects.filter(quantity_in_stock__gt=0).values('id', 'name', 'sku', 'unit_price', 'quantity_in_stock')
    
    return render(request, 'sales/sale_form.html', {
        'form': form,
        'formset': formset,
        'products': products,
        'sale': sale,
        'is_edit': True
    })

@login_required
@permission_required('sales.delete_sale', raise_exception=True)
def sale_delete(request, pk):
    """View for deleting a sale"""
    sale = get_object_or_404(Sale, pk=pk)
    
    # Only allow deleting sales that are not too old (e.g., within 24 hours)
    time_threshold = timezone.now() - timezone.timedelta(hours=24)
    if sale.created_at < time_threshold:
        messages.error(request, "Cannot delete sales older than 24 hours")
        return redirect('sales:sale_detail', pk=sale.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Return stock quantities
                for item in sale.items.all():
                    product = item.product
                    product.quantity_in_stock += item.quantity
                    product.save()
                
                # Log activity before deletion
                invoice_number = sale.invoice_number
                ActivityLog.objects.create(
                    user=request.user,
                    action='delete',
                    entity_type='sale',
                    entity_id=sale.id,
                    description=f"Deleted sale with invoice #{invoice_number}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Delete the sale
                sale.delete()
                
                messages.success(request, f"Sale with invoice #{invoice_number} deleted successfully")
                return redirect('sales:sales_list')
        except Exception as e:
            messages.error(request, f"Error deleting sale: {str(e)}")
            return redirect('sales:sale_detail', pk=sale.id)
    
    return render(request, 'sales/sale_confirm_delete.html', {'sale': sale})

@login_required
def generate_receipt(request, pk):
    """Generate PDF receipt for a sale"""
    sale = get_object_or_404(Sale, pk=pk)
    
    # Prepare context for PDF template
    context = {
        'sale': sale,
        'company_name': settings.COMPANY_NAME,
        'company_address': settings.COMPANY_ADDRESS,
        'company_phone': settings.COMPANY_PHONE,
        'company_email': settings.COMPANY_EMAIL,
        'date': timezone.now().strftime('%Y-%m-%d'),
    }
    
    # Render HTML template
    template = get_template('sales/receipt_pdf.html')
    html = template.render(context)
    
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{sale.invoice_number}.pdf"'
    
    # Generate PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='download',
        entity_type='receipt',
        entity_id=sale.id,
        description=f"Downloaded receipt for invoice #{sale.invoice_number}",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return response

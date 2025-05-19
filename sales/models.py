from django.db import models
from django.utils import timezone
from inventory.models import Product
from users.models import CustomUser

class Sale(models.Model):
    """Model for sales transactions"""
    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    sale_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='cash')
    payment_status = models.CharField(max_length=20, default='paid')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.sale_date.strftime('%Y-%m-%d')}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate final amount"""
        if not self.final_amount:
            self.final_amount = self.total_amount - self.discount + self.tax
        super().save(*args, **kwargs)

class SaleItem(models.Model):
    """Model for individual items in a sale"""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity} units"
    
    def save(self, *args, **kwargs):
        """Override save to calculate total price and update inventory"""
        self.total_price = self.quantity * self.unit_price
        
        # Create inventory transaction for this sale item
        from inventory.models import InventoryTransaction
        
        # Check if this is a new sale item
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Only create transaction for new items to avoid duplicate inventory reductions
            InventoryTransaction.objects.create(
                product=self.product,
                transaction_type='sale',
                quantity=self.quantity,
                reference_id=f"SALE-{self.sale.invoice_number}",
                notes=f"Sale item for invoice #{self.sale.invoice_number}"
            )

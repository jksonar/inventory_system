from django.db import models
from django.utils import timezone

class Category(models.Model):
    """Model for product categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class Supplier(models.Model):
    """Model for product suppliers"""
    name = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    """Model for inventory products"""
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name='products')
    description = models.TextField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    reorder_quantity = models.PositiveIntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def is_low_stock(self):
        """Check if product is low in stock"""
        return self.quantity_in_stock <= self.reorder_level
    
    @property
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.quantity_in_stock == 0

class InventoryTransaction(models.Model):
    """Model to track inventory movements"""
    TRANSACTION_TYPES = (
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()  # Can be negative for sales/adjustments
    transaction_date = models.DateTimeField(default=timezone.now)
    reference_id = models.CharField(max_length=100, blank=True, null=True)  # For linking to sales or purchase orders
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.product.name} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Override save to update product quantity"""
        # Update product quantity based on transaction type
        if self.transaction_type == 'purchase' or self.transaction_type == 'return':
            self.product.quantity_in_stock += self.quantity
        elif self.transaction_type == 'sale':
            self.product.quantity_in_stock -= self.quantity
        elif self.transaction_type == 'adjustment':
            # For adjustments, quantity can be positive or negative
            self.product.quantity_in_stock += self.quantity
            
        self.product.save()
        super().save(*args, **kwargs)

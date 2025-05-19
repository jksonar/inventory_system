from django.db import models
from users.models import CustomUser

class Alert(models.Model):
    """Model for system alerts"""
    ALERT_TYPES = (
        ('low_stock', 'Low Stock Alert'),
        ('out_of_stock', 'Out of Stock Alert'),
        ('sales_milestone', 'Sales Milestone'),
        ('system', 'System Alert'),
    )
    
    ALERT_PRIORITIES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    priority = models.CharField(max_length=10, choices=ALERT_PRIORITIES, default='medium')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    target_users = models.ManyToManyField(CustomUser, related_name='alerts', blank=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)  # For linking to products, sales, etc.
    
    def __str__(self):
        return f"{self.title} ({self.alert_type})"

class ActivityLog(models.Model):
    """Model to track user activity"""
    ACTION_TYPES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    entity_type = models.CharField(max_length=50)  # e.g., 'product', 'sale', 'user'
    entity_id = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action} {self.entity_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

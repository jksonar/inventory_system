from django.db import models
from users.models import CustomUser

class Report(models.Model):
    """Model to store generated reports"""
    REPORT_TYPES = (
        ('sales', 'Sales Report'),
        ('inventory', 'Inventory Report'),
        ('low_stock', 'Low Stock Report'),
        ('custom', 'Custom Report'),
    )
    
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    file_path = models.FileField(upload_to='reports/')
    parameters = models.JSONField(blank=True, null=True)  # Store report parameters
    generated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='reports')
    generated_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.generated_at.strftime('%Y-%m-%d')}"

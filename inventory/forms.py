from django import forms
from .models import Category, Supplier, Product, InventoryTransaction

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = '__all__'

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

class InventoryTransactionForm(forms.ModelForm):
    class Meta:
        model = InventoryTransaction
        fields = '__all__'

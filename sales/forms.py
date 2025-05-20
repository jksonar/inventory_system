from django import forms
from .models import Sale, SaleItem

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = '__all__'

class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = '__all__'

SaleItemFormSet = forms.inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=1,
    can_delete=True
)

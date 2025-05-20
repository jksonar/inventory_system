from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'user_type', 'phone_number', 'address']

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'user_type', 'phone_number', 'address']

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone_number', 'address']

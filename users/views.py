from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm, ProfileEditForm

def is_admin(user):
    return user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def user_list(request):
    users = CustomUser.objects.all()
    return render(request, 'users/user_list.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def user_add(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users:user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/user_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def user_detail(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    return render(request, 'users/user_detail.html', {'user_obj': user})

@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('users:user_list')
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'users/user_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def user_delete(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user.delete()
        return redirect('users:user_list')
    return render(request, 'users/user_confirm_delete.html', {'user_obj': user})

@login_required
def profile(request):
    return render(request, 'users/profile.html', {'user': request.user})

@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('users:profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'users/profile_edit.html', {'form': form})

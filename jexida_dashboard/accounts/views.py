"""Account views for authentication."""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = request.POST.get("next", "/")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password")
    
    next_url = request.GET.get("next", "/")
    return render(request, "accounts/login.html", {
        "page_title": "Login",
        "next": next_url,
    })


def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect("accounts:login")


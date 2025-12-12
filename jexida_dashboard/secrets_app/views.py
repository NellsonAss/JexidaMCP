"""Views for secrets management."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse

from .models import Secret


def secret_list(request):
    """List all secrets."""
    service_type = request.GET.get("service_type")
    
    queryset = Secret.objects.all()
    if service_type:
        queryset = queryset.filter(service_type=service_type)
    
    secrets = queryset.order_by("service_type", "name")
    
    return render(request, "secrets/list.html", {
        "page_title": "Secrets",
        "secrets": secrets,
        "service_type_filter": service_type,
    })


def secret_create(request):
    """Create a new secret."""
    service_type = request.GET.get("service_type", "generic")
    
    # Pre-defined key templates for each service type
    key_templates = {
        "azure": ["tenant_id", "client_id", "client_secret", "subscription_id"],
        "unifi": ["controller_url", "username", "password", "site"],
        "synology": ["url", "username", "password"],
        "n8n": ["url", "username", "password", "encryption_key"],
        "generic": [],
    }
    
    if request.method == "POST":
        name = request.POST.get("name")
        service_type = request.POST.get("service_type")
        key = request.POST.get("key")
        value = request.POST.get("value")
        
        # Check for duplicate key within service type
        if Secret.objects.filter(service_type=service_type, key=key).exists():
            messages.error(
                request,
                f"A secret with key '{key}' already exists for {service_type}"
            )
            return render(request, "secrets/form.html", {
                "page_title": "New Secret",
                "secret": None,
                "service_type": service_type,
                "key_templates": key_templates.get(service_type, []),
            })
        
        try:
            secret = Secret(
                name=name,
                service_type=service_type,
                key=key,
            )
            secret.set_value(value)
            secret.save()
            
            messages.success(request, f"Secret '{name}' created successfully")
            return redirect("secrets:list")
        except Exception as e:
            messages.error(request, f"Failed to create secret: {e}")
    
    return render(request, "secrets/form.html", {
        "page_title": "New Secret",
        "secret": None,
        "service_type": service_type,
        "key_templates": key_templates.get(service_type, []),
    })


def secret_edit(request, secret_id):
    """Edit an existing secret."""
    secret = get_object_or_404(Secret, id=secret_id)
    
    if request.method == "POST":
        name = request.POST.get("name")
        value = request.POST.get("value")
        
        try:
            secret.name = name
            if value:  # Only update value if provided
                secret.set_value(value)
            secret.save()
            
            messages.success(request, f"Secret '{name}' updated successfully")
            return redirect("secrets:list")
        except Exception as e:
            messages.error(request, f"Failed to update secret: {e}")
    
    return render(request, "secrets/form.html", {
        "page_title": f"Edit Secret: {secret.name}",
        "secret": secret,
        "service_type": secret.service_type,
        "key_templates": [],
    })


def secret_delete(request, secret_id):
    """Delete a secret."""
    secret = get_object_or_404(Secret, id=secret_id)
    
    if request.method == "POST":
        name = secret.name
        secret.delete()
        messages.success(request, f"Secret '{name}' deleted successfully")
        return redirect("secrets:list")
    
    # GET request - show confirmation (usually handled by HTMX)
    return render(request, "secrets/delete_confirm.html", {
        "page_title": f"Delete Secret: {secret.name}",
        "secret": secret,
    })


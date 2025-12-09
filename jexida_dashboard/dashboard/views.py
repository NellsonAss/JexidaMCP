"""Dashboard views for main pages."""

import asyncio
from django.shortcuts import render
from django.http import JsonResponse

# Import from core services
import sys
sys.path.insert(0, str(__file__).replace('/jexida_dashboard/dashboard/views.py', ''))
from core.services.monitoring import get_monitoring_data


def home(request):
    """Dashboard home page with overview."""
    # Get secret counts from secrets_app
    from secrets_app.models import Secret
    
    secret_counts = {}
    for service_type in ["azure", "unifi", "synology", "generic"]:
        count = Secret.objects.filter(service_type=service_type).count()
        secret_counts[service_type] = count
    
    total_secrets = sum(secret_counts.values())
    
    # Get monitoring data (run async function)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        monitoring_data = loop.run_until_complete(get_monitoring_data())
        loop.close()
    except Exception as e:
        monitoring_data = {}
    
    return render(request, "dashboard/home.html", {
        "page_title": "Dashboard",
        "secret_counts": secret_counts,
        "total_secrets": total_secrets,
        "monitoring_data": monitoring_data,
    })


def monitoring(request):
    """Monitoring dashboard with live data."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        monitoring_data = loop.run_until_complete(get_monitoring_data())
        loop.close()
    except Exception as e:
        monitoring_data = {}
    
    return render(request, "dashboard/monitoring.html", {
        "page_title": "Monitoring",
        "monitoring_data": monitoring_data,
    })


def health(request):
    """Health check endpoint."""
    return JsonResponse({
        "status": "healthy",
        "version": "0.1.0",
    })


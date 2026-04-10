import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta


def get_client_ip(request):
    """Obtiene la IP real del cliente considerando proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_rate_limit(ip_address, event_type, max_events=20, window_minutes=5):
    """
    Rate limiting simple: máximo X eventos del mismo tipo por IP en Y minutos.
    Retorna True si está dentro del límite, False si excede.
    """
    if not ip_address:
        return True
    
    from .models import TrackingEvent
    
    time_threshold = timezone.now() - timedelta(minutes=window_minutes)
    recent_count = TrackingEvent.objects.filter(
        ip_address=ip_address,
        event=event_type,
        created_at__gte=time_threshold
    ).count()
    
    return recent_count < max_events


@csrf_exempt
@require_http_methods(["POST"])
def track_event(request):
    """
    Endpoint para recibir eventos de tracking desde el frontend.
    
    POST /api/tracking/
    Body: { "event": "whatsapp_click", "payload": {...} }
    """
    from .models import TrackingEvent
    
    try:
        # Parsear JSON del body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'JSON inválido'
            }, status=400)
        
        # Validar campos requeridos
        event = data.get('event', '').strip()
        if not event:
            return JsonResponse({
                'status': 'error',
                'message': 'Campo "event" requerido'
            }, status=400)
        
        # Validar que el evento sea uno de los permitidos
        valid_events = [choice[0] for choice in TrackingEvent.EVENT_CHOICES]
        if event not in valid_events:
            event = 'other'
        
        payload = data.get('payload', {})
        
        # Validar tamaño del payload (máximo 10KB)
        payload_str = json.dumps(payload)
        if len(payload_str) > 10240:
            return JsonResponse({
                'status': 'error',
                'message': 'Payload demasiado grande (máximo 10KB)'
            }, status=400)
        
        # Obtener IP y user agent
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Rate limiting simple
        if not check_rate_limit(ip_address, event):
            return JsonResponse({
                'status': 'error',
                'message': 'Demasiados eventos, intenta más tarde'
            }, status=429)
        
        # Guardar evento
        TrackingEvent.objects.create(
            event=event,
            payload=payload,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return JsonResponse({
            'status': 'ok'
        })
        
    except Exception as e:
        # Log del error pero no exponer detalles al cliente
        return JsonResponse({
            'status': 'error',
            'message': 'Error interno del servidor'
        }, status=500)

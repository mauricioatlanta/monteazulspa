from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from apps.catalog.models import Product


def get_cart(request):
    """Obtiene el carrito de la sesión"""
    if 'cart' not in request.session:
        request.session['cart'] = {}
    return request.session['cart']


def cart_view(request):
    """Vista del carrito"""
    cart = get_cart(request)
    cart_items = []
    total = 0
    
    for product_slug, quantity in cart.items():
        try:
            product = Product.objects.select_related('category').prefetch_related('images').get(
                slug=product_slug,
                is_active=True,
                deleted_at__isnull=True
            )
            item_total = float(product.price) * quantity
            total += item_total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': item_total
            })
        except Product.DoesNotExist:
            # Si el producto ya no existe, lo removemos del carrito
            del cart[product_slug]
            request.session.modified = True
    
    return render(request, 'cart/view.html', {
        'cart_items': cart_items,
        'total': total,
    })


def cart_add(request, slug):
    """Agrega un producto al carrito"""
    if request.method != 'POST':
        return redirect('catalog:product_detail', slug=slug)
    
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True,
        deleted_at__isnull=True
    )
    
    # Verificar cantidad (evitar ValueError y valores inválidos)
    try:
        quantity = int(request.POST.get('quantity', 1) or 1)
    except (ValueError, TypeError):
        quantity = 1
    quantity = max(1, quantity)
    cart = get_cart(request)
    
    if product.stock == 0:
        messages.error(request, f'El producto {product.name} está agotado.')
        return redirect('catalog:product_detail', slug=slug)
    
    # Verificar stock disponible
    current_quantity = cart.get(slug, 0)
    if current_quantity + quantity > product.stock:
        messages.warning(request, f'Solo hay {product.stock} unidades disponibles de {product.name}.')
        quantity = product.stock - current_quantity
        if quantity <= 0:
            return redirect('catalog:product_detail', slug=slug)
    
    # Agregar al carrito
    if slug in cart:
        cart[slug] += quantity
    else:
        cart[slug] = quantity
    
    request.session.modified = True
    messages.success(request, f'{product.name} agregado al carrito.')
    
    if request.POST.get('redirect') == 'cart':
        return redirect('cart:view')
    return redirect('catalog:product_detail', slug=slug)


def cart_remove(request, slug):
    """Remueve un producto del carrito"""
    cart = get_cart(request)
    
    if slug in cart:
        product = get_object_or_404(Product, slug=slug)
        del cart[slug]
        request.session.modified = True
        messages.success(request, f'{product.name} removido del carrito.')
    
    return redirect('cart:view')


def cart_update(request, slug):
    """Actualiza la cantidad de un producto en el carrito"""
    if request.method != 'POST':
        return redirect('cart:view')
    
    cart = get_cart(request)
    try:
        quantity = int(request.POST.get('quantity', 1) or 1)
    except (ValueError, TypeError):
        quantity = 1
    
    if slug not in cart:
        return redirect('cart:view')
    
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True,
        deleted_at__isnull=True
    )
    
    if quantity <= 0:
        del cart[slug]
        messages.success(request, f'{product.name} removido del carrito.')
    elif quantity > product.stock:
        messages.warning(request, f'Solo hay {product.stock} unidades disponibles.')
        quantity = product.stock
        cart[slug] = quantity
    else:
        cart[slug] = quantity
        messages.success(request, f'Cantidad de {product.name} actualizada.')
    
    request.session.modified = True
    return redirect('cart:view')


def cart_count(request):
    """Devuelve el número de items en el carrito (para AJAX)"""
    cart = get_cart(request)
    total_items = sum(cart.values())
    return JsonResponse({'count': total_items})


def _cart_items_and_total(request):
    """Devuelve lista de dicts con product, quantity, total y el total general (para checkout)."""
    cart = get_cart(request)
    items = []
    total = 0
    for product_slug, quantity in cart.items():
        try:
            product = Product.objects.get(
                slug=product_slug,
                is_active=True,
                deleted_at__isnull=True
            )
            unit_price = int(product.price)
            line_total = unit_price * quantity
            total += line_total
            items.append({
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            })
        except Product.DoesNotExist:
            continue
    return items, total



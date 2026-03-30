/**
 * Sistema de tracking persistente para Monteazul SPA
 * Envía eventos al backend sin romper UX si falla
 */

(function() {
    'use strict';

    const TRACKING_ENDPOINT = '/api/tracking/';
    const DEBUG = false; // Cambiar a true para ver logs en consola

    /**
     * Envía un evento de tracking al backend
     * @param {string} event - Tipo de evento (whatsapp_click, search, product_click, etc.)
     * @param {object} payload - Datos adicionales del evento
     */
    function trackEvent(event, payload = {}) {
        // Siempre hacer console.log para debugging local
        if (DEBUG || typeof console !== 'undefined') {
            console.log('[Tracking]', event, payload);
        }

        // Enviar a dataLayer de Google Analytics si existe
        if (typeof window.dataLayer !== 'undefined') {
            window.dataLayer.push({
                event: event,
                ...payload
            });
        }

        // Enviar al backend (try/catch para no romper UX)
        try {
            fetch(TRACKING_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    event: event,
                    payload: payload
                }),
                // No esperar respuesta para no bloquear UX
                keepalive: true
            }).catch(function(error) {
                // Silenciar errores de red para no molestar al usuario
                if (DEBUG) {
                    console.warn('[Tracking] Error al enviar evento:', error);
                }
            });
        } catch (error) {
            // Silenciar cualquier error
            if (DEBUG) {
                console.warn('[Tracking] Error en trackEvent:', error);
            }
        }
    }

    /**
     * Tracking de clicks en WhatsApp
     */
    function setupWhatsAppTracking() {
        document.addEventListener('click', function(e) {
            const target = e.target.closest('a[href*="wa.me"], a[href*="whatsapp"], a[href*="api.whatsapp.com"]');
            if (target) {
                const href = target.getAttribute('href') || '';
                const text = target.textContent.trim();
                
                trackEvent('whatsapp_click', {
                    url: href,
                    text: text,
                    page: window.location.pathname
                });
            }
        });
    }

    /**
     * Tracking de búsquedas
     */
    function setupSearchTracking() {
        // Tracking de búsqueda por texto
        const searchForms = document.querySelectorAll('form[action*="buscar"], form[action*="search"]');
        searchForms.forEach(function(form) {
            form.addEventListener('submit', function(e) {
                const input = form.querySelector('input[type="search"], input[type="text"], input[name="q"]');
                if (input && input.value.trim()) {
                    trackEvent('search', {
                        query: input.value.trim(),
                        type: 'text',
                        page: window.location.pathname
                    });
                }
            });
        });

        // Tracking de búsqueda por vehículo
        const vehicleForms = document.querySelectorAll('form[action*="vehiculo"], form[action*="validar-vehiculo"]');
        vehicleForms.forEach(function(form) {
            form.addEventListener('submit', function(e) {
                const brand = form.querySelector('select[name="brand"]');
                const model = form.querySelector('select[name="model"]');
                const year = form.querySelector('select[name="year"]');
                
                if (brand && model && year) {
                    trackEvent('vehicle_search', {
                        brand: brand.options[brand.selectedIndex]?.text || '',
                        model: model.options[model.selectedIndex]?.text || '',
                        year: year.value,
                        page: window.location.pathname
                    });
                }
            });
        });
    }

    /**
     * Tracking de clicks en productos
     */
    function setupProductClickTracking() {
        document.addEventListener('click', function(e) {
            const target = e.target.closest('a[href*="/productos/"]');
            if (target) {
                const href = target.getAttribute('href') || '';
                const productName = target.querySelector('[data-product-name]')?.getAttribute('data-product-name') ||
                                  target.textContent.trim();
                const sku = target.querySelector('[data-sku]')?.getAttribute('data-sku') || '';
                
                trackEvent('product_click', {
                    url: href,
                    product_name: productName,
                    sku: sku,
                    page: window.location.pathname
                });
            }
        });
    }

    /**
     * Tracking de agregar al carrito
     */
    function setupAddToCartTracking() {
        document.addEventListener('click', function(e) {
            const target = e.target.closest('button[data-add-to-cart], .add-to-cart, button[type="submit"][form*="cart"]');
            if (target) {
                const sku = target.getAttribute('data-sku') || 
                          target.closest('[data-sku]')?.getAttribute('data-sku') || '';
                const productName = target.getAttribute('data-product-name') ||
                                  target.closest('[data-product-name]')?.getAttribute('data-product-name') || '';
                
                trackEvent('add_to_cart', {
                    sku: sku,
                    product_name: productName,
                    page: window.location.pathname
                });
            }
        });
    }

    /**
     * Inicializar tracking cuando el DOM esté listo
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setupWhatsAppTracking();
                setupSearchTracking();
                setupProductClickTracking();
                setupAddToCartTracking();
            });
        } else {
            setupWhatsAppTracking();
            setupSearchTracking();
            setupProductClickTracking();
            setupAddToCartTracking();
        }
    }

    // Exponer función global para tracking manual
    window.trackEvent = trackEvent;

    // Inicializar
    init();

})();

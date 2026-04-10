from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product

from .models import Order, OrderItem


class CheckoutTransferFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Escapes", slug="escapes")
        self.product = Product.objects.create(
            sku="MAZ-TEST-001",
            name="Silenciador de prueba",
            slug="silenciador-de-prueba",
            category=self.category,
            price=Decimal("49990.00"),
            stock=10,
        )

    def _set_cart(self, quantity=2):
        session = self.client.session
        session["cart"] = {self.product.slug: quantity}
        session.save()

    def test_checkout_post_redirects_to_transfer_checkout(self):
        self._set_cart()

        response = self.client.post(
            reverse("cart:checkout"),
            {
                "full_name": "Cliente Transferencia",
                "email": "cliente@example.com",
                "phone": "+56911111111",
            },
            follow=True,
        )

        order = Order.objects.get(email="cliente@example.com")
        transfer_url = reverse("cart:checkout_transfer", args=[order.id])

        self.assertEqual(response.redirect_chain, [(transfer_url, 302)])
        self.assertTemplateUsed(response, "cart/checkout_transfer.html")
        self.assertContains(response, "Pago por transferencia bancaria")
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Silenciador de prueba x2")
        self.assertContains(response, "76.572.475-9")
        self.assertNotContains(response, "Pagar con Webpay")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)

    def test_checkout_review_redirects_to_transfer_checkout(self):
        order = Order.objects.create(
            status=Order.Status.DRAFT,
            full_name="Cliente Transferencia",
            email="cliente2@example.com",
            phone="+56922222222",
            delivery_method="DELIVERY",
            subtotal=49990,
            shipping_cost=0,
            total=49990,
        )
        OrderItem.objects.create(
            order=order,
            product_id=self.product.id,
            slug=self.product.slug,
            name=self.product.name,
            unit_price=49990,
            quantity=1,
        )

        response = self.client.get(reverse("cart:checkout_review", args=[order.id]))

        self.assertRedirects(response, reverse("cart:checkout_transfer", args=[order.id]))

# Generated manually for tracking app

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TrackingEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(choices=[('whatsapp_click', 'Click en WhatsApp'), ('search', 'Búsqueda'), ('product_click', 'Click en producto'), ('vehicle_search', 'Búsqueda por vehículo'), ('add_to_cart', 'Agregar al carrito'), ('other', 'Otro')], db_index=True, max_length=50, verbose_name='Tipo de evento')),
                ('payload', models.JSONField(blank=True, default=dict, help_text='Información adicional del evento en formato JSON', verbose_name='Datos del evento')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha y hora')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='Dirección IP')),
                ('user_agent', models.CharField(blank=True, default='', max_length=500, verbose_name='User Agent')),
            ],
            options={
                'verbose_name': 'Evento de tracking',
                'verbose_name_plural': 'Eventos de tracking',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['-created_at', 'event'], name='tracking_tr_created_b8e4c5_idx')],
            },
        ),
    ]

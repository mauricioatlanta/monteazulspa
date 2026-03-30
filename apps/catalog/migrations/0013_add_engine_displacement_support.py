from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_add_product_view_stat"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicleengine",
            name="displacement_cc",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                db_index=True,
                help_text="Cilindrada del motor en centímetros cúbicos (cc).",
            ),
        ),
        migrations.AddField(
            model_name="productcompatibility",
            name="displacement_cc",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                db_index=True,
                help_text="Cilindrada objetivo en centímetros cúbicos (cc). Si está vacío, se usa la del motor.",
            ),
        ),
        migrations.AddIndex(
            model_name="productcompatibility",
            index=models.Index(
                fields=["brand", "model", "displacement_cc", "year_from", "year_to"],
                name="cat_pc_brand_model_cc_year_idx",
            ),
        ),
    ]


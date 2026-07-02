from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business_billing', '0024_populate_public_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='public_token',
            field=models.CharField(max_length=20, unique=True, blank=True, default=''),
        ),
    ]

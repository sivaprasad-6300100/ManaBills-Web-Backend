from django.db import migrations, models
import uuid


def populate_public_tokens(apps, schema_editor):
    Invoice = apps.get_model('business_billing', 'Invoice')
    for invoice in Invoice.objects.all():
        invoice.public_token = uuid.uuid4().hex[:12].upper()
        invoice.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('business_billing', '0022_alter_invoice_invoice_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='public_token',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.RunPython(populate_public_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='invoice',
            name='public_token',
            field=models.CharField(blank=True, default='', max_length=20, unique=True),
        ),
    ]
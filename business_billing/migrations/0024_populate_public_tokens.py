import uuid
from django.db import migrations


def populate_public_tokens(apps, schema_editor):
    Invoice = apps.get_model('business_billing', 'Invoice')
    for invoice in Invoice.objects.filter(public_token=''):
        invoice.public_token = uuid.uuid4().hex[:12].upper()
        invoice.save(update_fields=['public_token'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('business_billing', '0023_invoice_public_token'),
    ]

    operations = [
        migrations.RunPython(populate_public_tokens, reverse_noop),
    ]
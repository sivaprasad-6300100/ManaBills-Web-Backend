from django.db import migrations


class Migration(migrations.Migration):
    """
    Enable pg_trgm extension for PostgreSQL trigram search.
    Must run AFTER the initial migration (0001_initial).
    
    Trigram indexes enable fast fuzzy search on text fields like product names.
    Example: "iphone" matches "iPhone", "i phone", "i-phone" in < 10ms.
    """

    dependencies = [
        ('business_billing', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
        ),
    ]

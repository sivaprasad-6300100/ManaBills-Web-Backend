from django.core.management.base import BaseCommand
from business_billing.models import ShopScanner, ShopProfile

class Command(BaseCommand):
    help = "Auto-create or fix scanner_id for all existing shop profiles"

    def handle(self, *args, **kwargs):
        profiles = ShopProfile.objects.select_related("user").all()
        created_count = 0
        fixed_count = 0

        for profile in profiles:
            user = profile.user
            phone = getattr(user, 'mobile_number', '') or str(user.pk)
            scanner_id = f"mb-{phone}-001"

            scanner, created = ShopScanner.objects.get_or_create(
                user=user,
                defaults={"scanner_id": scanner_id, "is_active": True}
            )

            if created:
                created_count += 1
                self.stdout.write(f"✅ Created: {scanner_id}")
            elif not scanner.scanner_id:
                scanner.scanner_id = scanner_id
                scanner.save(update_fields=["scanner_id"])
                fixed_count += 1
                self.stdout.write(f"🔧 Fixed: {scanner_id}")

        self.stdout.write(f"\nDone! Created: {created_count}, Fixed: {fixed_count}")
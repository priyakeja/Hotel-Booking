"""Point the header/footer “Offers” links at the dedicated Offers page.

Seeded navigation still sent the Offers menu item to ``/hotels?featured=true``
(the hotel listing), which made the Offers page unreachable and highlighted the
wrong menu item. This is a one-off content correction; administrators can change
the links again from the admin at any time.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    NavLink = apps.get_model('content', 'NavLink')
    for link in NavLink.objects.filter(label__iexact='Offers'):
        # Only rewrite links that still point at the hotel listing.
        if 'hotels' in (link.url or ''):
            link.url = '/offers'
            link.save(update_fields=['url'])


def backwards(apps, schema_editor):
    NavLink = apps.get_model('content', 'NavLink')
    for link in NavLink.objects.filter(label__iexact='Offers', url='/offers'):
        link.url = '/hotels?featured=true'
        link.save(update_fields=['url'])


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0007_contactmessage_phone_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

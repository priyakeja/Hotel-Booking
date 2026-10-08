from django.db import migrations


def switch_to_rupee(apps, schema_editor):
    """Move sites still carrying the old dollar default over to rupees.

    The frontend renders whatever currency the CMS exposes, and the seeded
    SkyStay site shipped with '$'. Sites that already chose a different
    currency are left untouched.
    """
    SiteSettings = apps.get_model('content', 'SiteSettings')
    SiteSettings.objects.filter(currency_symbol='$').update(
        currency_symbol='₹',
        currency_code='INR',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0004_alter_sitesettings_currency_code_and_more'),
    ]

    operations = [
        migrations.RunPython(switch_to_rupee, migrations.RunPython.noop),
    ]

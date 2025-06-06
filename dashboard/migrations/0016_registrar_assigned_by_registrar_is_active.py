# Generated by Django 4.2.13 on 2025-05-10 00:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard', '0015_alter_registrar_teacher'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrar',
            name='assigned_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='registrar',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]

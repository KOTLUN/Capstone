# Generated by Django 4.2.13 on 2025-05-06 00:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0011_student_student_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='suffix',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]

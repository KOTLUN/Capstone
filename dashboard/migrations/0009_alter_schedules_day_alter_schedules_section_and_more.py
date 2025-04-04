# Generated by Django 4.2.13 on 2025-03-23 04:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_grades'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schedules',
            name='day',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='schedules',
            name='section',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.sections'),
        ),
        migrations.AlterField(
            model_name='schedules',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.subject'),
        ),
        migrations.AlterField(
            model_name='schedules',
            name='teacher_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.teachers'),
        ),
    ]

# Generated by Django 4.2.13 on 2025-05-06 00:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0010_remove_student_status_student_force_password_change_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='student_status',
            field=models.CharField(choices=[('New Student', 'New Student'), ('Transferee', 'Transferee'), ('Returnee', 'Returnee')], default='New Student', max_length=20),
        ),
    ]

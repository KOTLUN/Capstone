# Generated by Django 4.2.13 on 2025-03-21 05:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_student_student_photo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Guardian',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('middle_name', models.CharField(blank=True, max_length=100, null=True)),
                ('last_name', models.CharField(max_length=100)),
                ('contact_number', models.CharField(max_length=15)),
                ('relationship', models.CharField(choices=[('Parent', 'Parent'), ('Guardian', 'Guardian'), ('Sibling', 'Sibling'), ('Relative', 'Other Relative')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guardians', to='dashboard.student')),
            ],
        ),
    ]

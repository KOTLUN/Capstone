# Generated by Django 4.2.13 on 2025-03-21 06:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_guardian'),
    ]

    operations = [
        migrations.CreateModel(
            name='Grades',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_year', models.CharField(max_length=9)),
                ('q1_grade', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('q2_grade', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('q3_grade', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('q4_grade', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('final_grade', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='dashboard.student')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.subject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dashboard.teachers')),
            ],
            options={
                'verbose_name': 'Grade',
                'verbose_name_plural': 'Grades',
                'unique_together': {('student', 'subject', 'teacher', 'school_year')},
            },
        ),
    ]

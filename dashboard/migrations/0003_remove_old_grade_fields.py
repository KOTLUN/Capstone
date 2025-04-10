from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_update_grades_structure'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE dashboard_grades
            DROP COLUMN q1_grade,
            DROP COLUMN q2_grade,
            DROP COLUMN q3_grade,
            DROP COLUMN q4_grade,
            DROP COLUMN final_grade,
            DROP COLUMN date_updated,
            DROP COLUMN old_grade;
            """,
            reverse_sql="""
            ALTER TABLE dashboard_grades
            ADD COLUMN q1_grade decimal(5,2) NULL,
            ADD COLUMN q2_grade decimal(5,2) NULL,
            ADD COLUMN q3_grade decimal(5,2) NULL,
            ADD COLUMN q4_grade decimal(5,2) NULL,
            ADD COLUMN final_grade decimal(5,2) NULL,
            ADD COLUMN date_updated datetime(6) NULL,
            ADD COLUMN old_grade decimal(5,2) NULL;
            """
        ),
    ] 
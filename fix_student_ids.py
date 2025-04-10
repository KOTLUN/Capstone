"""
One-time script to fix student IDs in the grades table.
Run with: python manage.py shell < fix_student_ids.py
"""

from dashboard.models import Grades, Student, Enrollment
from django.db import connection

# Get student ID mappings (numeric ID → correct ID)
students = Student.objects.all()
id_mappings = {}

for student in students:
    try:
        # Convert student ID to number by stripping leading zeros
        numeric_id = int(student.student_id.lstrip('0'))
        id_mappings[numeric_id] = student.student_id
        print(f"Mapped: {numeric_id} → {student.student_id}")
    except (ValueError, AttributeError):
        continue

# Print current grades with student IDs
print("\nCurrent grades:")
with connection.cursor() as cursor:
    cursor.execute("SELECT id, student_id, subject_id, grade, quarter FROM dashboard_grades")
    for row in cursor.fetchall():
        grade_id, student_id, subject_id, grade, quarter = row
        print(f"Grade ID: {grade_id}, Student ID: {student_id}, Subject: {subject_id}, Quarter: {quarter}, Grade: {grade}")

# Update student IDs in grades table
print("\nUpdating student IDs...")
updated = 0
with connection.cursor() as cursor:
    for numeric_id, correct_id in id_mappings.items():
        cursor.execute(
            "UPDATE dashboard_grades SET student_id = %s WHERE student_id = %s",
            [correct_id, numeric_id]
        )
        updated += cursor.rowcount
        if cursor.rowcount > 0:
            print(f"Updated {cursor.rowcount} grades: {numeric_id} → {correct_id}")

print(f"\nTotal grades updated: {updated}")

# Print updated grades
print("\nUpdated grades:")
with connection.cursor() as cursor:
    cursor.execute("SELECT id, student_id, subject_id, grade, quarter FROM dashboard_grades")
    for row in cursor.fetchall():
        grade_id, student_id, subject_id, grade, quarter = row
        print(f"Grade ID: {grade_id}, Student ID: {student_id}, Subject: {subject_id}, Quarter: {quarter}, Grade: {grade}") 
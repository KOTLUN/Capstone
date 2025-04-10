from django.db import connection

# First, print the current grades
with connection.cursor() as cursor:
    cursor.execute("SELECT id, student_id, subject_id, grade, quarter FROM dashboard_grades")
    print("Current grades:")
    for row in cursor.fetchall():
        grade_id, student_id, subject_id, grade, quarter = row
        print(f"Grade ID: {grade_id}, Student ID: {student_id}, Subject: {subject_id}, Quarter: {quarter}, Grade: {grade}")

# Now update student ID from 5 to 55555
with connection.cursor() as cursor:
    cursor.execute("UPDATE dashboard_grades SET student_id = %s WHERE student_id = %s", ['55555', '5'])
    print(f"\nUpdated {cursor.rowcount} rows from student_id 5 to 55555")

# Print the updated grades
with connection.cursor() as cursor:
    cursor.execute("SELECT id, student_id, subject_id, grade, quarter FROM dashboard_grades")
    print("\nUpdated grades:")
    for row in cursor.fetchall():
        grade_id, student_id, subject_id, grade, quarter = row
        print(f"Grade ID: {grade_id}, Student ID: {student_id}, Subject: {subject_id}, Quarter: {quarter}, Grade: {grade}")

print("\nUpdate complete!") 
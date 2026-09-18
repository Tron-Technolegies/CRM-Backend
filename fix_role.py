import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM.settings')
django.setup()

from AdminApp.models import Staff

staff = Staff.objects.get(id=5)
old_role = staff.role
staff.role = 'sales agent'
staff.save(update_fields=['role'])

print(f"Updated Staff id=5 ({staff.full_name}): '{old_role}' → '{staff.role}'")
print("Done. Emil joy can now access all sales agent endpoints including picklists.")

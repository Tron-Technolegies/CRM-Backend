import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CRM.settings')
django.setup()

from AdminApp.models import Staff
from AdminApp.permissions import ROLE_PERMISSIONS, has_permission

VALID_ROLES = set(ROLE_PERMISSIONS.keys())
print('Valid roles:', VALID_ROLES)
print()

print('=== Staff with INVALID roles ===')
found = False
for s in Staff.objects.select_related('company').all():
    role = (s.role or '').strip().lower()
    if role not in VALID_ROLES:
        print(f'  Staff id={s.id} | name={s.full_name} | role="{s.role}" | company={s.company}')
        found = True
if not found:
    print('  (none - all roles are valid)')

print()
print('=== picklist.view permission check per staff ===')
for s in Staff.objects.select_related('company').all():
    ok = has_permission(s, 'picklist.view')
    print(f'  [{"OK" if ok else "DENIED"}] Staff id={s.id} | name={s.full_name} | role="{s.role}" | company={s.company}')

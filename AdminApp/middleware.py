from django.http import JsonResponse
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import User


class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public_paths = [
            "/api/admin/staff/login/",
            "/api/admin/staff/signup/",
            "/api/admin/auth/verify-invite/",
            "/api/admin/staff/acceptinvitation/",
            "/api/token/",
            "/api/token/refresh/",
            "/admin/",
        ]

        if any(request.path.startswith(path) for path in public_paths):
            return self.get_response(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse({"message": "Authentication required"}, status=401)

        token = auth_header.split(" ")[1]

        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            user = User.objects.select_related("staff__company").get(id=user_id)
            staff = user.staff
            request.company = staff.company
            request.staff = staff

        except Exception as e:
            print("MIDDLEWARE ERROR:", e)
            return JsonResponse({"message": str(e)}, status=401)

        return self.get_response(request)
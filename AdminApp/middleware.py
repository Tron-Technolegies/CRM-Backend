from django.http import JsonResponse
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import User


class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print("PATH:", request.path)
        print("AUTH HEADER:", request.headers.get("Authorization"))

        public_paths = [
            "/api/admin/staff/login/",
            "/api/admin/staff/signup/",
            "/api/admin/auth/verify-invite/",
            "/api/admin/staff/acceptinvitation/",
            "/api/token/",
            "/api/token/refresh/",
            "/admin/",
            "/api/admin/integrations/meta/callback/",
            "/api/admin/webhooks/meta/",
            # Gmail OAuth callback: Google redirects the browser here without a JWT
            "/api/admin/email/callback/",
            # --- Twilio webhooks: hit directly by Twilio's servers, no JWT ---
            "/api/admin/calls/connect-twiml/",
            "/api/admin/calls/status-callback/",
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
            staff = getattr(user, "staff", None)
            if not staff and user.email:
                from AdminApp.models import Staff
                staff = Staff.objects.select_related("company").filter(email__iexact=user.email).first()
            if not staff and user.id in (2, 4):
                from AdminApp.models import Staff
                staff = Staff.objects.select_related("company").filter(id=1).first()
            request.user = user
            request.staff = staff
            request.company = staff.company if staff else None

        except Exception as e:
            print("MIDDLEWARE ERROR:", e)
            return JsonResponse({"message": str(e)}, status=401)

        return self.get_response(request)
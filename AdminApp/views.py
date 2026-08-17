import os
import traceback
from urllib.parse import urlencode
from venv import logger
from django.core import signing
from django.shortcuts import redirect

from django.tasks import task
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
import requests
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.db.models import Sum
from django.db.models.functions import TruncWeek
from django.db.models import Count
from django.db import transaction

from AdminApp.models import Accounts, Address, Call, Case, CaseSolution, Company, Customer, Deal, Invoice, InvoiceItem, Lead, Meeting, PicklistOption, PriceBook, PriceBookItem, Product, PurchaseOrder, PurchaseOrderItem, QuoteProduct, Quotes, SalesOrder, SalesOrderItem, Service, Staff, Task, Vendor

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import send_mail

from django.db.models import Q
from rest_framework import status
from django.template.loader import render_to_string
from io import BytesIO
from xhtml2pdf import pisa
from django.utils.dateparse import parse_date

from AdminApp.services import create_lead_for_company, get_related_label, notify_user

from .models import MetaIntegration


# .............. authentication..............
@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def user_signup(request):


    name = request.data.get("name", "").strip()
    email = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")

    company_name = request.data.get("company_name", "").strip()
    company_email = request.data.get("company_email", "").strip().lower()
    company_phone = request.data.get("company_phone", "").strip()
    company_website = request.data.get("company_website", "").strip()

    if not name:
        return Response({"message": "Name is required"}, status=400)

    if not email:
        return Response({"message": "Email is required"}, status=400)

    if not password:
        return Response({"message": "Password is required"}, status=400)
    
    if len(password) < 8:
            return Response({"message": "Password must be at least 8 characters long"}, status=400)
    
    if not company_name:
        return Response({"message": "Company name is required"}, status=400)

    if not company_email:
        return Response({"message": "Company email is required"}, status=400)


    if User.objects.filter(email=email).exists():
        return Response(
            {"message": "User email already exists"},
            status=400
        )


    if Company.objects.filter(email=company_email).exists():
        return Response(
            {"message": "Company email already exists"},
            status=400
        )


    company = Company.objects.create(
        name=company_name,
        email=company_email,
        phone=company_phone,
        website=company_website,
    )


    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
    )


    staff = Staff.objects.create(
        company=company,
        user=user,
        full_name=name,
        email=email,
        role="admin",
        department="Management",
        is_invited=False,
        is_accepted=True,
    )

    refresh = RefreshToken.for_user(user)

    return Response({

        "message": "Company created successfully",

        "access": str(refresh.access_token),
        "refresh": str(refresh),

        "user": {

            "id": user.id,
            "name": user.first_name,
            "email": user.email,

            "role": staff.role,

            "companyId": company.id,
            "companyName": company.name,

        }

    })



@api_view(["POST"])
@permission_classes([AllowAny])
def user_login(request):

    email = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")

    if not email:
        return Response(
            {"message": "Email is required"},
            status=400
        )

    if not password:
        return Response(
            {"message": "Password is required"},
            status=400
        )

    try:
        user_obj = User.objects.get(email=email)

    except User.DoesNotExist:

        return Response(
            {"message": "Invalid email or password"},
            status=401
        )

    user = authenticate(
        username=user_obj.username,
        password=password
    )

    if user is None:

        return Response(
            {"message": "Invalid email or password"},
            status=401
        )

    try:

        staff = Staff.objects.select_related("company").get(user=user)

    except Staff.DoesNotExist:

        return Response(
            {"message": "Staff profile not found"},
            status=404
        )

    if not staff.company.is_active:

        return Response(
            {"message": "Your company has been deactivated."},
            status=403
        )

    if not staff.is_accepted:

        return Response(
            {"message": "Your account is not activated."},
            status=403
        )

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)

    return JsonResponse({

        "access": str(refresh.access_token),
        "refresh": str(refresh),

        "user": {

            "id": user.id,
            "name": user.first_name,
            "email": user.email,

            "role": staff.role,

            "companyId": staff.company.id,
            "companyName": staff.company.name,

        }

    })



@api_view(['POST'])
def user_logout(request):
    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logged out successfully"})
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def accept_invitation(request):

    token = request.data.get("token")
    password = request.data.get("password")

    if not token or not password:
        return Response(
            {
                "message": "Token and password are required."
            },
            status=400
        )

    try:
        staff = Staff.objects.get(

            invitation_token=token,
            is_accepted=False,

        )

    except Staff.DoesNotExist:

        return Response(
            {"message": "Invalid invitation."}, status=400)

    user = User.objects.create_user(

        username=staff.email,
        email=staff.email,
        password=password,
        first_name=staff.full_name,

    )

    staff.user = user
    staff.is_invited = False
    staff.is_accepted = True
    staff.invitation_token = None

    print("Before save:", staff.is_invited)

    staff.save()

    staff.refresh_from_db()

    print("After save:", staff.is_invited)

    refresh = RefreshToken.for_user(user)

    return Response({

        "message": "Account created successfully",
        "access": str(refresh.access_token),
        "refresh": str(refresh),

    })


    



# ..............lead.......................
@api_view(["GET"])
def meta_connect(request):

    state = signing.dumps(
        {
            "company_id": request.company.id,
        },
        salt="meta-oauth"
    )

    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "config_id": settings.META_CONFIG_ID,
        "state": state,
        "response_type": "code",
    }

    meta_url = (
        "https://www.facebook.com/v24.0/dialog/oauth?"
        + urlencode(params)
    )

    return JsonResponse({
        "auth_url": meta_url
    })

# @api_view(["GET"])
# def meta_callback(request):

#     code = request.GET.get("code")
#     state = request.GET.get("state")

#     if not code:
#         return JsonResponse(
#             {"error": "Authorization code not received from Meta"},
#             status=400
#         )

#     if not state:
#         return JsonResponse(
#             {"error": "State not received"},
#             status=400
#         )

#     # Verify state
#     try:
#         state_data = signing.loads(
#             state,
#             salt="meta-oauth",
#             max_age=600
#         )

#         company_id = state_data["company_id"]

#     except signing.BadSignature:
#         return JsonResponse(
#             {"error": "Invalid or expired state"},
#             status=400
#         )

#     # Exchange code for access token
#     try:
#         response = requests.get(
#             "https://graph.facebook.com/v24.0/oauth/access_token",
#             params={
#                 "client_id": settings.META_APP_ID,
#                 "client_secret": settings.META_APP_SECRET,
#                 "redirect_uri": settings.META_REDIRECT_URI,
#                 "code": code,
#             },
#             timeout=30
#         )

#         data = response.json()

#     except requests.RequestException as e:
#         return JsonResponse(
#             {"error": f"Meta connection failed: {str(e)}"},
#             status=500
#         )

#     if "access_token" not in data:
#         return JsonResponse(
#             {
#                 "error": "Failed to get Meta access token",
#                 "details": data
#             },
#             status=400
#         )

#     access_token = data["access_token"]

#     # Get Meta user
#     me_response = requests.get(
#         "https://graph.facebook.com/v24.0/me",
#         params={
#             "fields": "id,name",
#             "access_token": access_token,
#         },
#         timeout=30
#     )

#     me_data = me_response.json()

#     if "error" in me_data:
#         return JsonResponse(
#             {
#                 "error": "Failed to get Meta user",
#                 "details": me_data
#             },
#             status=400
#         )

#     # Get Ad Accounts
#     ad_response = requests.get(
#         "https://graph.facebook.com/v24.0/me/adaccounts",
#         params={
#             "fields": "id,name,account_id",
#             "access_token": access_token,
#         },
#         timeout=30
#     )

#     ad_data = ad_response.json()

#     if "error" in ad_data:
#         return JsonResponse(
#             {
#                 "error": "Failed to get Ad Accounts",
#                 "details": ad_data
#             },
#             status=400
#         )

#     return JsonResponse({
#         "message": "Meta authorization successful",
#         "company_id": company_id,
#         "meta_user": me_data,
#         "ad_accounts": ad_data.get("data", []),
#     })
@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def meta_callback(request):
    try:
        code = request.GET.get("code")
        state = request.GET.get("state")

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        settings_page = f"{frontend_url}/settings/notifications"

        if not code:
            return redirect(f"{settings_page}?meta=error&reason=no_code")

        if not state:
            return redirect(f"{settings_page}?meta=error&reason=no_state")

        try:
            state_data = signing.loads(state, salt="meta-oauth", max_age=600)
            company_id = state_data["company_id"]
        except signing.BadSignature:
            return redirect(f"{settings_page}?meta=error&reason=bad_state")

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return redirect(f"{settings_page}?meta=error&reason=company_not_found")

        try:
            response = requests.get(
                "https://graph.facebook.com/v24.0/oauth/access_token",
                params={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "redirect_uri": settings.META_REDIRECT_URI,
                    "code": code,
                },
                timeout=30
            )
            data = response.json()
        except requests.RequestException:
            return redirect(f"{settings_page}?meta=error&reason=token_exchange_failed")

        if "access_token" not in data:
            print("META TOKEN EXCHANGE RESPONSE:", data)
            return redirect(f"{settings_page}?meta=error&reason=no_access_token")

        access_token = data["access_token"]

        me_response = requests.get(
            "https://graph.facebook.com/v24.0/me",
            params={"fields": "id,name", "access_token": access_token},
            timeout=30
        )
        me_data = me_response.json()

        if "error" in me_data:
            print("META USER FETCH ERROR:", me_data)
            return redirect(f"{settings_page}?meta=error&reason=meta_user_failed")

        ad_response = requests.get(
            "https://graph.facebook.com/v24.0/me/adaccounts",
            params={"fields": "id,name,account_id", "access_token": access_token},
            timeout=30
        )
        ad_data = ad_response.json()

        if "error" in ad_data:
            print("META AD ACCOUNTS ERROR:", ad_data)
            return redirect(f"{settings_page}?meta=error&reason=ad_accounts_failed")

        ad_accounts = ad_data.get("data", [])
        first_ad_account_id = ad_accounts[0]["id"] if ad_accounts else None

        MetaIntegration.objects.update_or_create(
            company=company,
            defaults={
                "meta_user_id": me_data.get("id"),
                "access_token": access_token,
                "ad_account_id": first_ad_account_id,
                "assigned_staff": request.staff if hasattr(request, "staff") else None,
                "is_active": True,
            },
        )

        return redirect(f"{settings_page}?meta=connected")

    except Exception:
        print("META CALLBACK CRASHED:")
        print(traceback.format_exc())
        return redirect(f"{settings_page}?meta=error&reason=unhandled_exception")
 
 
@api_view(["GET"])
def meta_status(request):
    integration = MetaIntegration.objects.filter(
        company=request.company,
        is_active=True,
    ).first()
 
    if not integration:
        return JsonResponse({"connected": False})
 
    return JsonResponse({
        "connected": True,
        "metaUserId": integration.meta_user_id,
        "adAccountId": integration.ad_account_id,
        "pageId": integration.page_id,
        "connectedAt": integration.created_at.isoformat(),
    })



@api_view(["GET", "POST"])
def meta_webhook(request):

    # Meta webhook verification
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        verify_token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        expected_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN")

        if mode == "subscribe" and verify_token == expected_token:
            return JsonResponse(
                int(challenge),
                safe=False
            )

        return JsonResponse(
            {"error": "Verification failed"},
            status=403
        )

    # Meta webhook events
    if request.method == "POST":
        print("Meta webhook received:", request.data)

        return JsonResponse({
            "message": "Meta webhook received"
        })

    

@api_view(["POST"])
def add_lead(request):
    full_name = request.data.get("full_name")
    phone_number = request.data.get("phone_number")

    if not full_name or not phone_number:
        return HttpResponse(
            "Full name and phone number are mandatory fields",
            status=400
        )

    try:
        assigned_to_id = request.data.get("assigned_to")

        assigned_to = None

        if assigned_to_id:
            assigned_to = Staff.objects.get(
                id=assigned_to_id,
                company=request.company
            )

        lead = create_lead_for_company(
            company=request.company,
            full_name=full_name,
            phone_number=phone_number,
            email=request.data.get("email"),
            company_name=request.data.get("company_name", ""),
            lead_source=request.data.get("lead_source", "Website"),
            assigned_to=assigned_to,
            priority=request.data.get("priority", "Medium"),
            lead_description=request.data.get("lead_description"),
        )

        return HttpResponse(
            "Lead created successfully",
            status=201
        )

    except Staff.DoesNotExist:
        return HttpResponse(
            "Staff not found",
            status=404
        )

    except Exception as e:
        logger.exception("ADD LEAD ERROR")
        return HttpResponse(
            str(e),
            status=500
        )



@api_view(['GET'])
def view_leads(request):
    leads = Lead.objects.filter(company=request.company).order_by('-updated_at')
    list = []

    for i in leads:
        list.append(
            {
                "c_name": i.company.name,
                "id": i.id,
                "name": i.full_name,
                "phone": i.phone_number,
                "email": i.email,
                "companyName": i.company_name,
                "source": i.lead_source,
                "assignedTo": i.assigned_to.full_name if i.assigned_to else "—",
                "assignedToId": i.assigned_to.id if i.assigned_to else None,
                "status": i.get_status_display(),
                "priority": i.priority,
                "description": i.lead_description,
                "dateAdded": i.created_at.strftime("%b %d, %Y") if i.created_at else "—",
                "createdAt": i.created_at.isoformat() if i.created_at else None,
            }
        )
    return JsonResponse(list, safe=False)



@api_view(['GET'])
def view_single_lead(request, id):
    lead = get_object_or_404(Lead, id=id, company=request.company)
    
    data = {
                "id": lead.id,
                "name": lead.full_name,
                "phone": lead.phone_number,
                "email": lead.email,
                "companyName": lead.company_name,
                "source": lead.lead_source,
                "assignedTo": lead.assigned_to.full_name if lead.assigned_to else "—",
                "assignedToId": lead.assigned_to.id if lead.assigned_to else None, 
                "status": lead.get_status_display(),
                "priority": lead.priority,
                "description": lead.lead_description,
                "dateAdded": lead.created_at.strftime("%b %d, %Y") if lead.created_at else "—",
                "createdAt": lead.created_at.isoformat() if lead.created_at else None,
            }
    
    return JsonResponse(data, safe=False)
    


@api_view(['PUT'])
def update_lead(request, id):
    print("UPDATE DATA:", request.data)
    try:
        lead = Lead.objects.get(id=id, company=request.company)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    previous_staff_id = lead.assigned_to_id

    lead.full_name = request.data.get("full_name") or lead.full_name
    lead.phone_number = request.data.get("phone_number") or lead.phone_number
    lead.email = request.data.get("email") or lead.email
    lead.company_name = request.data.get("company_name") or lead.company_name
    lead.lead_source = request.data.get("lead_source") or lead.lead_source
    lead.priority = request.data.get("priority") or lead.priority
    lead.status = request.data.get("status") or lead.status
    lead.expected_closing_date = request.data.get("expected_closing_date") or None
    lead.lead_description = request.data.get("lead_description") or lead.lead_description

    assigned_to_id = request.data.get("assigned_to")
    if assigned_to_id:
        try:
            lead.assigned_to = Staff.objects.get(id=assigned_to_id)
        except Staff.DoesNotExist:
            return HttpResponse("Staff not found", status=404)
    else:
        lead.assigned_to = None

    try:
        lead.save()

        if lead.assigned_to and lead.assigned_to_id != previous_staff_id and lead.assigned_to.user:
            try:
                notify_user(
                    company=request.company,
                    user=lead.assigned_to.user,
                    notification_type="lead_assigned",
                    title="Lead Assigned to You",
                    message=(
                        f"Hello {lead.assigned_to.full_name},\n\n"
                        f"A lead has been reassigned to you.\n\n"
                        f"Lead: {lead.full_name}\n"
                        f"Company: {lead.company_name}\n"
                        f"Priority: {lead.priority}\n\n"
                        f"Please log in to the CRM to view the lead details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned lead %s", lead.id)

        return HttpResponse("Lead updated successfully", status=200)
    except Exception as e:
        print("SAVE ERROR:", str(e))
        return HttpResponse(str(e), status=500)



@api_view(['DELETE'])
def delete_lead(request, id):
    data = Lead.objects.get(id=id, company=request.company)
    data.delete()
    return JsonResponse({"message": "successfully deleted"})


# ...............deal....................
# ............ add lead id in add deal ..............
from .models import Deal, Lead, Customer, Notification, NotificationPreference, Staff
from .models import Accounts  # adjust import path/name to match your app


def serialize_deal(deal):
    related = None
    if deal.customer_id:
        related = {
            "type": "customer",
            "id": deal.customer_id,
            "name": deal.customer.contact_name or deal.customer.company_name,
        }
    elif deal.account_id:
        related = {
            "type": "account",
            "id": deal.account_id,
            "name": deal.account.account_name,
        }

    return {
        "id": deal.id,
        "name": deal.deal_name,
        "company_name": deal.company_name,
        "stage": deal.stage,
        "value": float(deal.deal_amount) if deal.deal_amount else 0,
        "expectedCloseDate": str(deal.expected_close_date) if deal.expected_close_date else "—",
        "assignedTo": deal.assigned_to.full_name if deal.assigned_to else "—",
        "assignedToId": deal.assigned_to.id if deal.assigned_to else None,
        "source": deal.deal_source,
        "priority": deal.priority,
        "description": deal.deal_description,
        "createdAt": deal.created_at.isoformat() if deal.created_at else None,
        "relatedTo": related,
    }


def _resolve_related(request, related_type, related_id):
    """Returns (customer, account, error_message)."""
    if related_type == "customer" and related_id:
        customer = Customer.objects.filter(id=related_id, company=request.company).first()
        if not customer:
            return None, None, "Customer not found"
        return customer, None, None

    if related_type == "account" and related_id:
        account = Accounts.objects.filter(id=related_id, company=request.company).first()
        if not account:
            return None, None, "Account not found"
        return None, account, None

    # empty/"none"/None → clear both
    return None, None, None


@api_view(['POST'])
def add_deal(request):
    deal_name = request.data.get("deal_name")
    company_name = request.data.get("company_name")
    deal_amount = request.data.get("deal_amount")
    stage = request.data.get("stage")
    assigned_to = request.data.get("assigned_to")
    expected_close_date = request.data.get("expected_close_date")
    deal_source = request.data.get("deal_source")
    priority = request.data.get("priority")
    deal_description = request.data.get("deal_description")

    related_type = request.data.get("related_type")
    related_id = request.data.get("related_id")

    if not deal_name or not company_name:
        return HttpResponse(
            "Deal name and company name are mandatory fields",
            status=400
        )

    if related_type not in ("customer", "account") or not related_id:
        return HttpResponse(
            "A deal must be linked to a Customer or an Account",
            status=400
        )

    customer, account, err = _resolve_related(request, related_type, related_id)
    if err:
        return HttpResponse(err, status=404)

    try:
        deal = Deal.objects.create(
            company=request.company,
            deal_name=deal_name,
            company_name=company_name,
            deal_amount=deal_amount,
            stage=stage,
            assigned_to_id=assigned_to,
            expected_close_date=expected_close_date,
            deal_source=deal_source,
            priority=priority,
            deal_description=deal_description,
            customer=customer,
            account=account,
        )

        if deal.assigned_to and deal.assigned_to.user:
            try:
                notify_user(
                    company=request.company,
                    user=deal.assigned_to.user,
                    notification_type="deal_assigned",
                    title="New Deal Assigned",
                    message=(
                        f"Hello {deal.assigned_to.full_name},\n\n"
                        f"A new deal has been assigned to you.\n\n"
                        f"Deal: {deal.deal_name}\n"
                        f"Company: {deal.company_name}\n"
                        f"Stage: {deal.stage}\n"
                        f"Amount: {deal.deal_amount}\n\n"
                        f"Please log in to the CRM to view the deal details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for deal %s", deal.id)

        return HttpResponse("Deal created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_deals(request):
    deals = (
        Deal.objects
        .filter(company=request.company)
        .select_related('assigned_to', 'customer', 'account')
        .order_by('-updated_at')
    )
    return JsonResponse([serialize_deal(d) for d in deals], safe=False)


@api_view(['GET'])
def view_single_deals(request, id):
    deal = get_object_or_404(
        Deal.objects.select_related('assigned_to', 'customer', 'account'),
        id=id, company=request.company
    )
    return JsonResponse(serialize_deal(deal), safe=False)


@api_view(['PUT'])
def update_deal(request, id):
    try:
        deal = Deal.objects.get(id=id, company=request.company)
    except Deal.DoesNotExist:
        return HttpResponse("Deal not found", status=404)

    previous_staff_id = deal.assigned_to_id

    deal.deal_name = request.data.get("deal_name") or deal.deal_name
    deal.company_name = request.data.get("company_name") or deal.company_name
    deal.deal_amount = request.data.get("deal_amount") or deal.deal_amount
    deal.stage = request.data.get("stage") or deal.stage
    deal.expected_close_date = request.data.get("expected_close_date") or deal.expected_close_date
    deal.deal_source = request.data.get("deal_source") or deal.deal_source
    deal.priority = request.data.get("priority") or deal.priority
    deal.deal_description = request.data.get("deal_description") or deal.deal_description

    assigned_to_id = request.data.get("assigned_to")
    if assigned_to_id:
        deal.assigned_to = get_object_or_404(Staff, id=assigned_to_id)
    else:
        deal.assigned_to = None

    if "related_type" in request.data:
        related_type = request.data.get("related_type")
        related_id = request.data.get("related_id")

        if related_type not in ("customer", "account") or not related_id:
            return HttpResponse(
                "A deal must be linked to a Customer or an Account",
                status=400
            )

        customer, account, err = _resolve_related(request, related_type, related_id)
        if err:
            return HttpResponse(err, status=404)

        deal.customer = customer
        deal.account = account

    try:
        deal.save()

        if deal.assigned_to and deal.assigned_to_id != previous_staff_id and deal.assigned_to.user:
            try:
                notify_user(
                    company=request.company,
                    user=deal.assigned_to.user,
                    notification_type="deal_assigned",
                    title="Deal Assigned to You",
                    message=(
                        f"Hello {deal.assigned_to.full_name},\n\n"
                        f"A deal has been reassigned to you.\n\n"
                        f"Deal: {deal.deal_name}\n"
                        f"Company: {deal.company_name}\n"
                        f"Stage: {deal.stage}\n"
                        f"Amount: {deal.deal_amount}\n\n"
                        f"Please log in to the CRM to view the deal details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned deal %s", deal.id)

        return HttpResponse("Deal updated successfully", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_deal(request, id):
    deal = get_object_or_404(Deal, id=id, company=request.company)
    deal.delete()
    return JsonResponse({"message": "successfully deleted"})



# ...................customer...................
@api_view(['POST'])
def add_customer(request):
    print("CUSTOMER PAYLOAD:", request.data)
    company_name = request.data.get("company_name")
    contact_name = request.data.get("contact_name")
    phone_number = request.data.get("phone_number")
    email = request.data.get("email")
    industry = request.data.get("industry")
    status = request.data.get("status")
    lifetime_value = request.data.get("lifetime_value")
    deal_id = request.data.get("deal_id")
    lead_id = request.data.get("lead_id")   # ← new: optional lead link

    if not contact_name or not phone_number or not email:
        return HttpResponse(
            "Company name, contact name and phone number are mandatory fields",
            status=400
        )

    deal = None
    if deal_id:
        try:
            deal = Deal.objects.get(id=deal_id)
        except Deal.DoesNotExist:
            return HttpResponse("Deal not found", status=404)
    
    lead = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id, company=request.company)
        except Lead.DoesNotExist:
            return HttpResponse("Lead not found", status=404)

        if lead.status == "converted":
            return HttpResponse("Lead already converted to a customer", status=400)


    try:
        customer = Customer.objects.create(
            company=request.company,
            company_name=company_name,
            contact_name=contact_name,
            phone_number=phone_number,
            email=email,
            industry=industry,
            status=status,
            lifetime_value=lifetime_value,
        )

        if deal:
            deal.stage = "Won"
            deal.customer = customer
            deal.save()

        if lead:
            lead.status = "converted"
            lead.converted_at = timezone.now()
            lead.save()

        return HttpResponse("Customer created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)



@api_view(['GET'])
def view_customers(request):
    customers = Customer.objects.filter(company=request.company)
    data = []

    for i in customers:
        data.append({
                "c_name": i.company.name,
                "id": i.id,
                "companyName": i.company_name,
                "contactName": i.contact_name,
                "phone": i.phone_number,
                "email": i.email,
                "industry": i.industry,
                "status": i.get_status_display(),
                "lifetimeValue": float(i.lifetime_value) if i.lifetime_value else 0,
                "joinDate": i.created_at.strftime("%Y-%m-%d") if i.created_at else "—",
                "createdAt": i.created_at.isoformat() if i.created_at else None,
            })

    return JsonResponse(data, safe=False)



@api_view(['GET'])
def view_single_customer(request, id):
    customer = get_object_or_404(Customer, id=id, company=request.company)

    data = {
                "id": customer.id,
                "companyName": customer.company_name,
                "contactName": customer.contact_name,
                "phone": customer.phone_number,
                "email": customer.email,
                "industry": customer.industry,
                "status": customer.get_status_display(),
                "lifetimeValue": float(customer.lifetime_value) if customer.lifetime_value else 0,
                "joinDate": customer.created_at.strftime("%Y-%m-%d") if customer.created_at else "—",
                "createdAt": customer.created_at.isoformat() if customer.created_at else None,
            }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_customer(request, id):
    try:
        customer = Customer.objects.get(id=id, company=request.company)
    except Customer.DoesNotExist:
        return HttpResponse("Customer not found", status=404)

    customer.company_name = request.data.get("company_name") or customer.company_name
    customer.contact_name = request.data.get("contact_name") or customer.contact_name
    customer.phone_number = request.data.get("phone_number") or customer.phone_number
    customer.email = request.data.get("email") or customer.email
    customer.industry = request.data.get("industry") or customer.industry
    customer.status = request.data.get("status") or customer.status
    customer.lifetime_value = request.data.get("lifetime_value") or customer.lifetime_value

    try:
        customer.save()
        return HttpResponse("Customer updated successfully", status=200)

    except Exception as e:
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_customer(request, id):
    customer = Customer.objects.get(id=id, company=request.company)
    customer.delete()
    return JsonResponse({"message": "Customer deleted successfully"})



# .................task..................
@api_view(['POST'])
def add_task(request):
    title = request.data.get("title")
    description = request.data.get("description")
    assigned_to = request.data.get("assigned_to")
    priority = request.data.get("priority", "medium")
    status = request.data.get("status")
    due_date_raw = request.data.get("due_date")

    related_type = request.data.get("related_type", "none")
    related_lead_id = request.data.get("related_lead")
    related_contact_id = request.data.get("related_contact")
    related_deal_id = request.data.get("related_deal")
    related_account_id = request.data.get("related_account")

    if not title or not due_date_raw:
        return JsonResponse(
            {"error": "Title and due_date are mandatory fields"},
            status=400
        )

    due_date = parse_date(due_date_raw)
    if not due_date:
        return JsonResponse(
            {"error": "due_date must be a valid date (YYYY-MM-DD)"},
            status=400
        )

    status_map = {
        "pending": "pending",
        "in progress": "in_progress",
        "in_progress": "in_progress",
        "completed": "completed",
    }
    status = status_map.get(status.lower() if status else "pending", "pending")

    priority = priority.lower() if priority else "medium"
    priority_choices = {"low", "medium", "high"}
    if priority not in priority_choices:
        return JsonResponse(
            {"error": f"priority must be one of {sorted(priority_choices)}"},
            status=400
        )

    valid_related_types = {"lead", "contact", "deal", "account", "none"}
    if related_type not in valid_related_types:
        return JsonResponse(
            {"error": f"related_type must be one of {sorted(valid_related_types)}"},
            status=400
        )

    staff = None
    if assigned_to:
        try:
            staff = Staff.objects.get(id=assigned_to, company=request.company)
        except Staff.DoesNotExist:
            return JsonResponse({"error": "Invalid staff"}, status=400)

    lead = contact = deal = account = None
    try:
        if related_type == "lead" and related_lead_id:
            lead = Lead.objects.get(id=related_lead_id, company=request.company)
        elif related_type == "contact" and related_contact_id:
            contact = Customer.objects.get(id=related_contact_id, company=request.company)
        elif related_type == "deal" and related_deal_id:
            deal = Deal.objects.get(id=related_deal_id, company=request.company)
        elif related_type == "account" and related_account_id:
            account = Accounts.objects.get(id=related_account_id, company=request.company)
    except (Lead.DoesNotExist, Customer.DoesNotExist, Deal.DoesNotExist, Accounts.DoesNotExist):
        return JsonResponse({"error": "Invalid related record"}, status=400)

    try:
        with transaction.atomic():
            task = Task.objects.create(
                company=request.company,
                title=title,
                description=description,
                assigned_to=staff,
                lead=lead,
                contact=contact,
                deal=deal,
                account=account,
                priority=priority,
                status=status,
                due_date=due_date,
            )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    # Notification failure shouldn't undo a successful task creation
    if staff and staff.user:
        related_label = get_related_label(related_type, lead, contact, deal, account)
        try:
            notify_user(
                company=request.company,
                user=staff.user,
                notification_type="task_assigned",
                title="New Task Assigned",
                message=(
                    f"Hello {staff.full_name},\n\n"
                    f"A new task has been assigned to you.\n\n"
                    f"Task: {task.title}\n"
                    f"Priority: {task.priority}\n"
                    f"Due Date: {task.due_date}\n"
                    + (f"Related To: {related_label}\n" if related_label else "")
                    + "\nPlease log in to the CRM to view the task details."
                ),
            )
        except Exception:
            logger.exception("Failed to notify staff for task %s", task.id)

    return JsonResponse({
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "assignedTo": staff.id if staff else None,
        "assignedToName": staff.full_name if staff else None,
        "priority": task.priority,
        "status": task.status,
        "dueDate": task.due_date,
        "relatedType": related_type,
    }, status=201)

@api_view(['GET'])
def view_tasks(request):
    tasks = Task.objects.filter(company=request.company).select_related(
        "assigned_to", "lead", "contact", "deal", "account"
    )
    data = []

    for i in tasks:
        related_type = "lead" if i.lead else "contact" if i.contact else "deal" if i.deal else "account" if i.account else "none"
        related_name = (
            i.lead.full_name if i.lead else
            i.contact.company_name if i.contact else
            i.deal.deal_name if i.deal else
            i.account.account_name if i.account else "—"
        )
        related_id = i.lead_id or i.contact_id or i.deal_id or i.account_id

        data.append({
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "assignedTo": i.assigned_to.full_name if i.assigned_to else "—",
            "assignedToId": i.assigned_to.id if i.assigned_to else None,
            "relatedType": related_type,
            "relatedTo": related_name,
            "relatedToId": related_id,
            "priority": i.priority,
            "status": i.status,
            "dueDate": str(i.due_date) if i.due_date else None,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_task(request, id):
    task = get_object_or_404(
        Task.objects.select_related("assigned_to", "lead", "contact", "deal", "account"),
        id=id, company=request.company
    )

    related_type = "lead" if task.lead else "contact" if task.contact else "deal" if task.deal else "account" if task.account else "none"
    related_name = (
        task.lead.full_name if task.lead else
        task.contact.company_name if task.contact else
        task.deal.deal_name if task.deal else
        task.account.account_name if task.account else "—"
    )
    related_id = task.lead_id or task.contact_id or task.deal_id or task.account_id

    data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "assignedTo": task.assigned_to.full_name if task.assigned_to else "—",
        "assignedToId": task.assigned_to.id if task.assigned_to else None,
        "relatedType": related_type,
        "relatedTo": related_name,
        "relatedToId": related_id,
        "priority": task.priority,
        "status": task.status,
        "dueDate": str(task.due_date) if task.due_date else None,
        "createdAt": task.created_at.isoformat() if task.created_at else None,
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_task(request, id):
    try:
        task = Task.objects.get(id=id, company=request.company)
    except Task.DoesNotExist:
        return HttpResponse("Task not found", status=404)

    if "title" in request.data:
        task.title = request.data.get("title")
    if "description" in request.data:
        task.description = request.data.get("description")
    if "priority" in request.data:
        task.priority = request.data.get("priority")
    if "due_date" in request.data:
        task.due_date = request.data.get("due_date")

    if "status" in request.data:
        status_map = {
            "pending": "pending",
            "in progress": "in_progress",
            "in_progress": "in_progress",
            "completed": "completed",
        }
        raw_status = request.data.get("status")
        task.status = status_map.get(raw_status.lower() if raw_status else "", task.status)

    if "assigned_to" in request.data:
        assigned_to_id = request.data.get("assigned_to")
        if assigned_to_id:
            try:
                task.assigned_to = Staff.objects.get(id=assigned_to_id, company=request.company)
            except Staff.DoesNotExist:
                return HttpResponse("Invalid staff", status=400)
        else:
            task.assigned_to = None

    if "related_type" in request.data:
        related_type = request.data.get("related_type")
        task.lead = None
        task.contact = None
        task.deal = None
        task.account = None

        try:
            if related_type == "lead":
                lead_id = request.data.get("related_lead")
                task.lead = Lead.objects.get(id=lead_id, company=request.company) if lead_id else None
            elif related_type == "contact":
                contact_id = request.data.get("related_contact")
                task.contact = Customer.objects.get(id=contact_id, company=request.company) if contact_id else None
            elif related_type == "deal":
                deal_id = request.data.get("related_deal")
                task.deal = Deal.objects.get(id=deal_id, company=request.company) if deal_id else None
            elif related_type == "account":
                account_id = request.data.get("related_account")
                task.account = Accounts.objects.get(id=account_id, company=request.company) if account_id else None
        except (Lead.DoesNotExist, Customer.DoesNotExist, Deal.DoesNotExist, Accounts.DoesNotExist):
            return HttpResponse("Invalid related record", status=400)

    try:
        task.save()
        return HttpResponse("Task updated successfully", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_task(request, id):
    try:
        task = Task.objects.get(id=id, company=request.company)
    except Task.DoesNotExist:
        return HttpResponse("Task not found", status=404)

    task.delete()
    return JsonResponse({"message": "Task deleted successfully"})



# ............staff(user)...............
@api_view(["POST"])
def add_staff(request):

    full_name = request.data.get("full_name")
    email = request.data.get("email")
    role = request.data.get("role")
    department = request.data.get("department")

    if not full_name or not email or not role:
        return HttpResponse(
            "Full name, email and role are mandatory fields",
            status=400,
        )

    if Staff.objects.filter(email=email).exists():
        return HttpResponse(
            "Email already exists",
            status=400
        )

    try:

        staff = Staff.objects.create(

            company=request.company,
            full_name=full_name,
            email=email,
            role=role,
            department=department,
            is_invited=True,

        )

        invite_link = (
            f"http://localhost:5173/staff/signup/"
            f"?token={staff.invitation_token}"
        )

        subject = "You're invited to join CRM"

        message = f"""
Hello {staff.full_name},

You have been invited to join {request.company.name}.

Role : {staff.role}

Click the link below to create your account.

{invite_link}

Thank you.
"""

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [staff.email],
            fail_silently=False,
        )

        return HttpResponse( "Invitation sent successfully.", status=201)

    except Exception as e:
        return HttpResponse( str(e), status=500)
    


@api_view(['GET'])
def view_staff(request):
    staffs = Staff.objects.filter(company=request.company).select_related("user")
    data = []

    for i in staffs:
        data.append({
            "id": i.id,
            "fullName": i.full_name,
            "email": i.email,
            "role": i.role,
            "department": i.department,
            "status": "Invited" if i.is_invited else "Active",
            "invitedAt": i.invited_at.isoformat() if i.invited_at else None,
            "lastActive": i.user.last_login.isoformat() if i.user and i.user.last_login else None,
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_staff(request, id):
    staff = get_object_or_404(Staff.objects.select_related("company", "user"), id=id, company=request.company)

    data = {
                "c_id":staff.company.name,
                "id": staff.id,
                "fullName": staff.full_name,
                "email": staff.email,
                "role": staff.role,
                "department": staff.department,
                "status": "Invited" if staff.is_invited else "Active",
                "invitedAt": staff.invited_at.isoformat() if staff.invited_at else None,
                "lastActive": staff.user.last_login.isoformat() if staff.user and staff.user.last_login else None,
            }

    return JsonResponse(data, safe=False)

@api_view(['PUT'])
def update_staff(request, id):
    try:
        staff = Staff.objects.get(id=id, company=request.company)
    except Staff.DoesNotExist:
        return HttpResponse("Staff not found", status=404)

    staff.full_name = request.data.get("full_name") or staff.full_name
    staff.email = request.data.get("email") or staff.email

    try:
        staff.save()
        return HttpResponse("Staff updated successfully", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['DELETE'])
def delete_staff(request, id):
    staff = Staff.objects.get(id=id, company=request.company)
    staff.delete()
    return JsonResponse({"message": "Staff deleted successfully"})



# ............report.............
from datetime import datetime

@api_view(['GET'])
def report_view(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    leads_qs = Lead.objects.filter(company=request.company)
    deals_qs = Deal.objects.filter(company=request.company)
    customers_qs = Customer.objects.filter(company=request.company)
    tasks_qs = Task.objects.filter(company=request.company)

    if start_date and end_date:
        leads_qs = leads_qs.filter(created_at__date__range=[start_date, end_date])
        deals_qs = deals_qs.filter(created_at__date__range=[start_date, end_date])
        customers_qs = customers_qs.filter(created_at__date__range=[start_date, end_date])
        tasks_qs = tasks_qs.filter(created_at__date__range=[start_date, end_date])

    total_leads = leads_qs.count()
    total_deals = deals_qs.count()
    total_customers = customers_qs.count()
    total_tasks = tasks_qs.count()
    total_staff = Staff.objects.count()
    active_customers = customers_qs.filter(status="active").count()
    pending_tasks = tasks_qs.filter(status="pending").count()
    completed_tasks = tasks_qs.filter(status="completed").count()
    high_priority_tasks = tasks_qs.filter(priority="high").count()
    total_revenue = customers_qs.aggregate(total=Sum("lifetime_value"))["total"] or 0

    revenue_over_time_qs = (
        customers_qs
        .annotate(week=TruncWeek("created_at"))
        .values("week")
        .annotate(total=Sum("lifetime_value"))
        .order_by("week")
    )
    revenue_over_time = [
        {"date": entry["week"].strftime("%b %d"), "revenue": float(entry["total"] or 0)}
        for entry in revenue_over_time_qs
    ]

    leads_by_status_qs = leads_qs.values("status").annotate(count=Count("id"))
    leads_by_status = {entry["status"]: entry["count"] for entry in leads_by_status_qs}

    deals_by_stage_qs = deals_qs.values("stage").annotate(count=Count("id"))
    deals_by_stage = {entry["stage"]: entry["count"] for entry in deals_by_stage_qs}

    leads_by_source_qs = leads_qs.values("lead_source").annotate(count=Count("id"))
    leads_by_source = {entry["lead_source"]: entry["count"] for entry in leads_by_source_qs}

    leads_over_time_qs = (
        leads_qs
        .annotate(week=TruncWeek("created_at"))
        .values("week")
        .annotate(count=Count("id"))
        .order_by("week")
    )
    leads_over_time = [
        {"name": entry["week"].strftime("%b %d"), "value": entry["count"]}
        for entry in leads_over_time_qs
    ]

    report = {
        "total_leads": total_leads,
        "total_deals": total_deals,
        "total_customers": total_customers,
        "total_tasks": total_tasks,
        "total_staff": total_staff,
        "active_customers": active_customers,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "high_priority_tasks": high_priority_tasks,
        "total_revenue": float(total_revenue),
        "revenue_over_time": revenue_over_time,
        "leads_by_status": leads_by_status,
        "deals_by_stage": deals_by_stage,
        "leads_by_source": leads_by_source,
        "leads_over_time": leads_over_time,
    }

    return JsonResponse(report)



# ......... convert lead to customer through button ...........
@api_view(['GET'])
def get_lead_to_customer_prefill(request, lead_id):
    """Prefill customer form from lead data"""
    try:
        lead = Lead.objects.get(id=lead_id, company=request.company)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    if lead.status == "converted":
        return JsonResponse({"message": "Lead already converted to a customer"}, status=400)

    prefilled_data = {
        "lead_id": lead.id,
        "company_name": lead.company_name,
        "contact_name": lead.full_name,
        "phone_number": lead.phone_number,
        "email": lead.email,
        "assigned_to": lead.assigned_to_id,
        "industry": "",
    }

    return JsonResponse(prefilled_data, status=200)



@api_view(["POST"])
def convert_lead(request, lead_id):
    try:
        lead = Lead.objects.get(
            id=lead_id,
            company=request.company
        )
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    if lead.status == "converted":
        return HttpResponse("Lead already converted", status=400)

    create_customer = request.data.get("create_customer", False)
    create_account = request.data.get("create_account", False)
    create_deal = request.data.get("create_deal", False)

    customer = None
    account = None
    deal = None

    # ----------------------------
    # CUSTOMER
    # ----------------------------

    if create_customer:

        customer = Customer.objects.filter(
            lead=lead,
            company=request.company
        ).first()

        if customer is None:
            customer = Customer.objects.create(
                company=request.company,
                lead=lead,

                company_name=request.data.get(
                    "company_name",
                    lead.company_name,
                ),

                contact_name=request.data.get(
                    "contact_name",
                    lead.full_name,
                ),

                phone_number=request.data.get(
                    "phone_number",
                    lead.phone_number,
                ),

                email=request.data.get(
                    "email",
                    lead.email,
                ),

                industry=request.data.get("industry", ""),
            )

    # ----------------------------
    # ACCOUNT
    # ----------------------------

    if create_account:

        account = Accounts.objects.filter(
            company=request.company,
            account_name=lead.company_name,
        ).first()

        if account is None:
            account = Accounts.objects.create(
                company=request.company,

                account_name=request.data.get(
                    "company_name",
                    lead.company_name,
                ),

                assigned_to=lead.assigned_to,

                phone_number=request.data.get(
                    "phone_number",
                    lead.phone_number,
                ),

                website=request.data.get(
                    "website",
                    "",
                ),

                industry=request.data.get(
                    "industry",
                    "",
                ),
            )

    # ----------------------------
    # DEAL
    # ----------------------------

    if create_deal:

        related_type = request.data.get("related_type")

        deal_kwargs = {
            "company": request.company,
            "lead": lead,
            "deal_name": request.data.get("deal_name", f"{lead.company_name} Deal"),
            "deal_amount": request.data.get("deal_amount") or 0,
            "stage": request.data.get("stage") or "Proposal",
            "assigned_to_id": request.data.get("assigned_to") or None,
            "expected_close_date": request.data.get("expected_closing_date") or None,
            "deal_source": request.data.get("deal_source") or "",
            "priority": request.data.get("priority") or "Medium",
            "deal_description": request.data.get("description") or "",
        }

        if related_type == "customer":

            if customer is None:
                customer = Customer.objects.create(
                    company=request.company,
                    lead=lead,
                    company_name=lead.company_name,
                    contact_name=lead.full_name,
                    phone_number=lead.phone_number,
                    email=lead.email,
                    industry="",
                )

            deal = Deal.objects.create(
                customer=customer,
                account=None,
                **deal_kwargs,
            )

        elif related_type == "account":

            if account is None:
                account = Accounts.objects.create(
                    company=request.company,
                    account_name=lead.company_name,
                    assigned_to=lead.assigned_to,
                    phone_number=lead.phone_number,
                    website="",
                    industry="",
                )

            deal = Deal.objects.create(
                customer=None,
                account=account,
                **deal_kwargs,
            )

    # ----------------------------
    # UPDATE LEAD
    # ----------------------------

    lead.status = "converted"
    lead.converted_at = timezone.now()
    lead.save()

    return JsonResponse({
        "message": "Lead converted successfully",

        "customer_id": customer.id if customer else None,

        "account_id": account.id if account else None,

        "deal_id": deal.id if deal else None,
    })

    
# ............ unconverted lead show in dropdown ........
@api_view(['GET'])
def get_unconverted_leads(request):
    leads = Lead.objects.exclude(status="converted", company=request.company)
    data = []
    for lead in leads:
        data.append({
            "id": lead.id,
            "name": lead.full_name,
            "company_name": lead.company_name,
            "source": lead.lead_source,
        })
    return JsonResponse(data, safe=False)
# ............ connect the deal to customer ..............
@api_view(['GET'])
def get_linkable_deals(request):
    deals = Deal.objects.exclude(stage="Won")
    return JsonResponse([
        {
            "id": d.id,
            "name": d.deal_name,
            "company_name": d.company_name,
            "contact_name": d.lead.full_name if d.lead else "",
            "phone": d.lead.phone_number if d.lead else "",
            "email": d.lead.email if d.lead else "",
        }
        for d in deals
    ], safe=False)


# ......... view total leads ...........
@api_view(['GET'])
def leads_by_source(request):
    sources = (
        Lead.objects
        .filter(company=request.company)
        .values("lead_source")
        .annotate(count=Count("id"))
    )

    total = Lead.objects.filter(company=request.company).count()

    colors = {
        "Website": "#3B82F6",
        "WhatsApp": "#10B981",
        "Facebook Ads": "#8B5CF6",
        "Google Ads": "#F59E0B",
        "Referral": "#64748B",
        "Ads": "#F97316",
    }

    data = [
        {
            "name": source["lead_source"],
            "value": round((source["count"] / total) * 100) if total else 0,
            "color": colors.get(source["lead_source"], "#64748B"),
        }
        for source in sources
    ]

    return JsonResponse({
        "data": data,
        "total": total,
    })


# .......... Add, Edit, View, Delete the choices ...........

@api_view(['GET'])
def view_picklists(request):
    field = request.GET.get("field")
 
    qs = PicklistOption.objects.filter(
        Q(company=request.company) | Q(company__isnull=True),
        is_active=True,
    )
 
    if field:
        qs = qs.filter(field=field)
 
    data = [
        {"id": o.id, "field": o.field, "value": o.value, "label": o.label, "order": o.order}
        for o in qs
    ]
    return JsonResponse(data, safe=False)
 
 
@api_view(['POST'])
def add_picklist_option(request):
    field = request.data.get("field")
    value = request.data.get("value")
    label = request.data.get("label")
 
    if not field or not value or not label:
        return HttpResponse("field, value and label are required", status=400)
 
    exists = PicklistOption.objects.filter(
        Q(company=request.company) | Q(company__isnull=True),
        field=field,
        value=value,
    ).exists()
 
    if exists:
        return HttpResponse("This option already exists", status=400)
 
    max_order = PicklistOption.objects.filter(company=request.company, field=field).count()
    PicklistOption.objects.create(company=request.company, field=field, value=value, label=label, order=max_order)
    return HttpResponse("Option added successfully", status=201)
 
 
@api_view(['PUT'])
def update_picklist_option(request, id):
    try:
        option = PicklistOption.objects.get(id=id, company=request.company)
    except PicklistOption.DoesNotExist:
        return HttpResponse("Option not found", status=404)
 
    option.label = request.data.get("label") or option.label
    option.is_active = request.data.get("is_active", option.is_active)
    option.save()
    return HttpResponse("Option updated successfully", status=200)
 
 
@api_view(['DELETE'])
def delete_picklist_option(request, id):
    try:
        option = PicklistOption.objects.get(id=id, company=request.company)
        option.delete()
        return JsonResponse({"message": "Option deleted successfully"})
    except PicklistOption.DoesNotExist:
        return HttpResponse("Option not found", status=404)

# .............. account ................

@api_view(['POST'])
def add_account(request):
    account_name = request.data.get("acc_name")
    assigned_to_id = request.data.get("assigned_to")
    phone_number = request.data.get("phone")
    account_site = request.data.get("acc_site")
    parent_account_id = request.data.get("parent_acc")
    website = request.data.get("website")
    account_type = request.data.get("acc_type")
    industry = request.data.get("industry")
    ownership = request.data.get("ownership")
    employees = request.data.get("employees")
    billing_data = request.data.get("billing_add")  
    shipping_data = request.data.get("shipping_add")

    if not account_name or not phone_number:
        return HttpResponse("Account name and phone number are mandatory fields", status=400)

    try:
        billing_address = None
        if billing_data:
            billing_address = Address.objects.create(
                country=billing_data.get("country", ""),
                address=billing_data.get("address", ""),
                street_address=billing_data.get("street_add", ""),
                city=billing_data.get("city", ""),
                state=billing_data.get("state", ""),
                zip_code=billing_data.get("zip_code", ""),
            )

        shipping_address = None
        if shipping_data:
            shipping_address = Address.objects.create(
                country=shipping_data.get("country", ""),
                address=shipping_data.get("address", ""),
                street_address=shipping_data.get("street_add", ""),
                city=shipping_data.get("city", ""),
                state=shipping_data.get("state", ""),
                zip_code=shipping_data.get("zip_code", ""),
            )

        Accounts.objects.create(
            company=request.company,
            account_name=account_name,
            assigned_to_id=assigned_to_id,
            phone_number=phone_number,
            account_site=account_site,
            parent_account_id=parent_account_id,
            website=website,
            account_type=account_type,
            industry=industry,
            ownership=ownership,
            employees=employees,
            billing_address=billing_address,
            shipping_address=shipping_address,
        )
        return HttpResponse("Account created successfully", status=201)

    except Exception as e:
        print("ADD ACCOUNT ERROR:", str(e))
        return HttpResponse(str(e), status=500)
    

@api_view(['GET'])
def view_accounts(request):
    accounts = Accounts.objects.filter(company=request.company).select_related(
        "billing_address", "shipping_address", "assigned_to", "parent_account"
    ).all()

    data = []
    for i in accounts:
        data.append({
            "id": i.id,
            "account_name": i.account_name,
            "assigned_to": i.assigned_to.id if i.assigned_to else None,
            "assigned_to_name": str(i.assigned_to) if i.assigned_to else None,
            "phone_number": i.phone_number,
            "account_site": i.account_site,
            "parent_account": i.parent_account.id if i.parent_account else None,
            "website": i.website,
            "account_type": i.account_type,
            "industry": i.industry,
            "ownership": i.ownership,
            "employees": i.employees,

            "billing_address": {
                "id": i.billing_address.id,
                "country": i.billing_address.country,
                "address": i.billing_address.address,
                "street_address": i.billing_address.street_address,
                "city": i.billing_address.city,
                "state": i.billing_address.state,
                "zip_code": i.billing_address.zip_code,
            } if i.billing_address else None,
            
            "shipping_address": {
                "id": i.shipping_address.id,
                "country": i.shipping_address.country,
                "address": i.shipping_address.address,
                "street_address": i.shipping_address.street_address,
                "city": i.shipping_address.city,
                "state": i.shipping_address.state,
                "zip_code": i.shipping_address.zip_code,
            } if i.shipping_address else None,
            "created_at": i.created_at.isoformat(),
            "updated_at": i.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_account(request, id):
    account = get_object_or_404(
        Accounts.objects.select_related("billing_address", "shipping_address", "assigned_to", "parent_account"),
        id=id, company=request.company
    )

    data = {
        "id": account.id,
        "account_name": account.account_name,
        "assigned_to": account.assigned_to.id if account.assigned_to else None,
        "assigned_to_name": str(account.assigned_to) if account.assigned_to else None,
        "phone_number": account.phone_number,
        "account_site": account.account_site,
        "parent_account": account.parent_account.id if account.parent_account else None,
        "website": account.website,
        "account_type": account.account_type,
        "industry": account.industry,
        "ownership": account.ownership,
        "employees": account.employees,

        "billing_address": {
            "id": account.billing_address.id,
            "country": account.billing_address.country,
            "address": account.billing_address.address,
            "street_address": account.billing_address.street_address,
            "city": account.billing_address.city,
            "state": account.billing_address.state,
            "zip_code": account.billing_address.zip_code,
        } if account.billing_address else None,

        "shipping_address": {
            "id": account.shipping_address.id,
            "country": account.shipping_address.country,
            "address": account.shipping_address.address,
            "street_address": account.shipping_address.street_address,
            "city": account.shipping_address.city,
            "state": account.shipping_address.state,
            "zip_code": account.shipping_address.zip_code,
        } if account.shipping_address else None,

        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_account(request, id):
    try:
        account = Accounts.objects.get(id=id, company=request.company)
    except Accounts.DoesNotExist:
        return HttpResponse("Account not found", status=404)

    try:
        account.account_name = request.data.get("acc_name") or account.account_name
        account.phone_number = request.data.get("phone") or account.phone_number
        account.account_site = request.data.get("acc_site") or account.account_site
        account.website = request.data.get("website") or account.website
        account.account_type = request.data.get("acc_type") or account.account_type
        account.industry = request.data.get("industry") or account.industry
        account.ownership = request.data.get("ownership") or account.ownership
        account.employees = request.data.get("employees") or account.employees

        assigned_to_id = request.data.get("assigned_to")
        if assigned_to_id:
            account.assigned_to_id = assigned_to_id

        parent_account_id = request.data.get("parent_acc")
        if parent_account_id:
            account.parent_account_id = parent_account_id

        billing_data = request.data.get("billing_add")
        if billing_data:
            if account.billing_address:
                account.billing_address.country = billing_data.get("country", account.billing_address.country)
                account.billing_address.address = billing_data.get("address", account.billing_address.address)
                account.billing_address.street_address = billing_data.get("street_add", account.billing_address.street_address)
                account.billing_address.city = billing_data.get("city", account.billing_address.city)
                account.billing_address.state = billing_data.get("state", account.billing_address.state)
                account.billing_address.zip_code = billing_data.get("zip_code", account.billing_address.zip_code)
                account.billing_address.save()
            else:
                billing_address = Address.objects.create(
                    country=billing_data.get("country", ""),
                    address=billing_data.get("address", ""),
                    street_address=billing_data.get("street_add", ""),
                    city=billing_data.get("city", ""),
                    state=billing_data.get("state", ""),
                    zip_code=billing_data.get("zip_code", ""),
                )
                account.billing_address = billing_address

        shipping_data = request.data.get("shipping_add")
        if shipping_data:
            if account.shipping_address:
                account.shipping_address.country = shipping_data.get("country", account.shipping_address.country)
                account.shipping_address.address = shipping_data.get("address", account.shipping_address.address)
                account.shipping_address.street_address = shipping_data.get("street_add", account.shipping_address.street_address)
                account.shipping_address.city = shipping_data.get("city", account.shipping_address.city)
                account.shipping_address.state = shipping_data.get("state", account.shipping_address.state)
                account.shipping_address.zip_code = shipping_data.get("zip_code", account.shipping_address.zip_code)
                account.shipping_address.save()
            else:
                shipping_address = Address.objects.create(
                    country=shipping_data.get("country", ""),
                    address=shipping_data.get("address", ""),
                    street_address=shipping_data.get("street_add", ""),
                    city=shipping_data.get("city", ""),
                    state=shipping_data.get("state", ""),
                    zip_code=shipping_data.get("zip_code", ""),
                )
                account.shipping_address = shipping_address

        account.save()
        return HttpResponse("Account updated successfully", status=200)

    except Exception as e:
        print("UPDATE ACCOUNT ERROR:", str(e))
        return HttpResponse(str(e), status=500)



@api_view(['DELETE'])
def delete_account(request, id):
    account = Accounts.objects.get(id=id, company=request.company)
    account.delete()
    return JsonResponse({"message": "Account deleted successfully"})



# ................. quotes ..................
# Helper to serialize products
def _serialize_products(quote):
    products = []
    for item in quote.items.all():
        products.append({
            "productId": item.product.id,
            "product": item.product.name,
            "description": item.description,
            "quantity": item.quantity,
            "listPrice": float(item.list_price),
            "amount": float(item.amount),
            "discount": float(item.discount),
            "tax": float(item.tax),
            "lineTotal": float(item.total),
        })
    return products

# Helper to serialize addresses
def _serialize_address(addr):
    if not addr:
        return None

    return {
        "country": addr.country,
        "address": addr.address,
        "street_address": addr.street_address,
        "city": addr.city,
        "state": addr.state,
        "zipCode": addr.zip_code,
    }


@api_view(['POST'])
def add_quote(request):
    subject = request.data.get("subject")
    quote_stage = request.data.get("quote_stage", "draft")
    valid_until = request.data.get("valid_until")
    assigned_to_id = request.data.get("assigned_to")
    deal_id = request.data.get("deal_id")
    contact_name = request.data.get("contact_name", "")

    account_id = request.data.get("account_id")
    customer_id = request.data.get("customer_id")

    billing_data = request.data.get("billing_add")
    shipping_data = request.data.get("shipping_add")

    products_data = request.data.get("products", [])

    if not subject:
        return HttpResponse("Subject is required", status=400)

    try:
        deal = None
        account = None
        customer = None

        if deal_id:
            deal = get_object_or_404(
                Deal,
                id=deal_id,
                company=request.company
            )

        # Account: explicit account_id wins, otherwise derive from the deal
        if account_id:
            account = get_object_or_404(
                Accounts.objects.select_related(
                    "billing_address",
                    "shipping_address"
                ),
                id=account_id,
                company=request.company,
            )
        elif deal and deal.account_id:
            account = deal.account

        # Customer: same pattern — explicit wins, otherwise derive from the deal
        if customer_id:
            customer = get_object_or_404(
                Customer,
                id=customer_id,
                company=request.company,
            )
        elif deal and deal.customer_id:
            customer = deal.customer

        with transaction.atomic():

            billing_address = None
            if billing_data:
                billing_address = Address.objects.create(**billing_data)
            elif account and account.billing_address:
                src = account.billing_address
                billing_address = Address.objects.create(
                    country=src.country,
                    address=src.address,
                    street_address=src.street_address,
                    city=src.city,
                    state=src.state,
                    zip_code=src.zip_code,
                )

            shipping_address = None
            if shipping_data:
                shipping_address = Address.objects.create(**shipping_data)
            elif account and account.shipping_address:
                src = account.shipping_address
                shipping_address = Address.objects.create(
                    country=src.country,
                    address=src.address,
                    street_address=src.street_address,
                    city=src.city,
                    state=src.state,
                    zip_code=src.zip_code,
                )

            quote = Quotes.objects.create(
                company=request.company,
                subject=subject,
                quote_stage=quote_stage,
                valid_until=valid_until or None,
                assigned_to_id=assigned_to_id or None,
                deal=deal,
                account=account,
                customer=customer,
                contact_name=contact_name,
                billing_address=billing_address,
                shipping_address=shipping_address,
            )

            for item in products_data:

                product = get_object_or_404(
                    Product,
                    id=item.get("product"),
                    company=request.company,
                )

                quantity = int(item.get("quantity", 1))
                list_price = float(product.unit_price)
                discount = float(item.get("discount", 0))
                tax = float(product.tax_percentage)

                amount = quantity * list_price
                discounted_amount = amount - discount
                tax_amount = discounted_amount * tax / 100
                total = discounted_amount + tax_amount

                QuoteProduct.objects.create(
                    quote=quote,
                    product=product,
                    description=item.get(
                        "description",
                        product.description
                    ),
                    quantity=quantity,
                    list_price=list_price,
                    amount=amount,
                    discount=discount,
                    tax=tax,
                    total=total,
                )

        return HttpResponse(
            "Quote created successfully",
            status=201,
        )

    except Exception as e:
        print("ADD QUOTE ERROR:", str(e))
        return HttpResponse(str(e), status=500)
    
    

@api_view(['GET'])
def view_quotes(request):
    quotes = (
        Quotes.objects.filter(company=request.company)
        .select_related(
            "assigned_to",
            "deal",
            "account",
            "customer",
            "billing_address",
            "shipping_address",
        )
        .prefetch_related("items__product")
        .order_by("-updated_at")
    )

    data = []

    for quote in quotes:
        grand_total = sum(item.total for item in quote.items.all())

        data.append({
            "id": quote.id,
            "subject": quote.subject,
            "quoteStage": quote.quote_stage,
            "validUntil": str(quote.valid_until) if quote.valid_until else None,
            "contactName": quote.contact_name,
            "assignedToId": quote.assigned_to_id,
            "quoteOwner": quote.assigned_to.full_name if quote.assigned_to else "",
            "dealId": quote.deal_id,
            "dealName": quote.deal.deal_name if quote.deal else "",
            "accountId": quote.account_id,
            "accountName": quote.account.account_name if quote.account else "",
            "customerId": quote.customer_id,
            "customerName": quote.customer.company_name if quote.customer else "",
            "billingAddress": _serialize_address(quote.billing_address),
            "shippingAddress": _serialize_address(quote.shipping_address),
            "products": _serialize_products(quote),
            "grandTotal": float(grand_total),
            "createdAt": quote.created_at.isoformat(),
            "updatedAt": quote.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_quote(request, id):

    quote = get_object_or_404(
        Quotes.objects.select_related(
            "assigned_to",
            "deal",
            "account",
            "customer",
            "billing_address",
            "shipping_address",
        ).prefetch_related("items__product"),
        id=id,
        company=request.company,
    )

    data = {
        "id": quote.id,
        "subject": quote.subject,
        "quoteStage": quote.quote_stage,
        "validUntil": str(quote.valid_until) if quote.valid_until else None,
        "contactName": quote.contact_name,
        "assignedToId": quote.assigned_to_id,
        "dealId": quote.deal_id,
        "dealName": quote.deal.deal_name if quote.deal else "",
        "accountId": quote.account_id,
        "accountName": quote.account.account_name if quote.account else "",
        "customerId": quote.customer_id,
        "customerName": quote.customer.company_name if quote.customer else "",
        "billingAddress": _serialize_address(quote.billing_address),
        "shippingAddress": _serialize_address(quote.shipping_address),
        "products": _serialize_products(quote),
    }

    return JsonResponse(data)

@api_view(['PUT'])
def update_quote(request, id):

    quote = get_object_or_404(
        Quotes,
        id=id,
        company=request.company
    )

    try:
        with transaction.atomic():

            quote.subject = request.data.get("subject", quote.subject)
            quote.quote_stage = request.data.get("quote_stage", quote.quote_stage)
            quote.valid_until = request.data.get("valid_until") or None
            quote.contact_name = request.data.get("contact_name", quote.contact_name)

            # Assigned To
            assigned_to = request.data.get("assigned_to")
            quote.assigned_to_id = assigned_to if assigned_to else None

            # Deal
            deal_id = request.data.get("deal_id")
            if deal_id:
                quote.deal = get_object_or_404(
                    Deal,
                    id=deal_id,
                    company=request.company
                )
            else:
                quote.deal = None

            # Account: explicit account_id wins, otherwise derive from the deal
            account_id = request.data.get("account_id")
            if account_id:
                quote.account = get_object_or_404(
                    Accounts,
                    id=account_id,
                    company=request.company
                )
            elif quote.deal and quote.deal.account_id:
                quote.account = quote.deal.account
            else:
                quote.account = None

            # Customer: explicit customer_id wins, otherwise derive from the deal
            customer_id = request.data.get("customer_id")
            if customer_id:
                quote.customer = get_object_or_404(
                    Customer,
                    id=customer_id,
                    company=request.company
                )
            elif quote.deal and quote.deal.customer_id:
                quote.customer = quote.deal.customer
            else:
                quote.customer = None

            # Billing Address
            billing_data = request.data.get("billing_add")
            if billing_data:
                if quote.billing_address:
                    for key, value in billing_data.items():
                        setattr(quote.billing_address, key, value)
                    quote.billing_address.save()
                else:
                    quote.billing_address = Address.objects.create(**billing_data)

            # Shipping Address
            shipping_data = request.data.get("shipping_add")
            if shipping_data:
                if quote.shipping_address:
                    for key, value in shipping_data.items():
                        setattr(quote.shipping_address, key, value)
                    quote.shipping_address.save()
                else:
                    quote.shipping_address = Address.objects.create(**shipping_data)

            quote.save()

            products_data = request.data.get("products")

            if products_data is not None:

                quote.items.all().delete()

                for item in products_data:

                    product = get_object_or_404(
                        Product,
                        id=item.get("product"),
                        company=request.company,
                    )

                    quantity = int(item.get("quantity", 1))
                    list_price = float(product.unit_price)
                    discount = float(item.get("discount", 0))
                    tax = float(product.tax_percentage)

                    amount = quantity * list_price
                    discounted = amount - discount
                    tax_amount = discounted * tax / 100
                    total = discounted + tax_amount

                    QuoteProduct.objects.create(
                        quote=quote,
                        product=product,
                        description=item.get(
                            "description",
                            product.description
                        ),
                        quantity=quantity,
                        list_price=list_price,
                        amount=amount,
                        discount=discount,
                        tax=tax,
                        total=total,
                    )

        return HttpResponse(
            "Quote updated successfully",
            status=200
        )

    except Exception as e:
        print("UPDATE QUOTE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(["DELETE"])
def delete_quote(request, id):
    try:
        quote = Quotes.objects.get(id=id, company=request.company)

        quote.delete()

        return Response(
            {"message": "Quote deleted successfully"},
            status=status.HTTP_200_OK
        )

    except Quotes.DoesNotExist:
        return Response(
            {"error": "Quote not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    

# .................. meeting ...............
@api_view(['POST'])
def add_meeting(request):
    title = request.data.get("title")
    meeting_venue = request.data.get("meeting_venue", "online")
    provider = request.data.get("provider", "")
    location = request.data.get("location", "")
    all_day = request.data.get("all_day", False)
    from_datetime = request.data.get("from_datetime")
    to_datetime = request.data.get("to_datetime")
    host_id = request.data.get("host")
    participant_ids = request.data.get("participants", [])
    related_type = request.data.get("related_type", "none")
    related_lead_id = request.data.get("related_lead")
    related_customer_id = request.data.get("related_customer")
    related_account_id = request.data.get("related_account")
    repeat = request.data.get("repeat", "none")

    if not title or not from_datetime or not to_datetime:
        return HttpResponse("Title, from_datetime and to_datetime are required", status=400)

    try:
        meeting = Meeting.objects.create(
            company=request.company,
            title=title,
            meeting_venue=meeting_venue,
            provider=provider if meeting_venue == "online" else "",
            location=location if meeting_venue != "online" else "",
            all_day=all_day if meeting_venue != "online" else False,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            host_id=host_id or None,
            related_type=related_type,
            related_lead_id=related_lead_id if related_type == "lead" else None,
            related_customer_id=related_customer_id if related_type == "customer" else None,
            related_account_id=related_account_id if related_type == "account" else None,
            repeat=repeat,
        )

        if participant_ids:
            meeting.participants.set(participant_ids)

        if meeting.host and meeting.host.user:
            try:
                notify_user(
                    company=request.company,
                    user=meeting.host.user,
                    notification_type="meeting_reminder",
                    title="New Meeting Scheduled",
                    message=(
                        f"Hello {meeting.host.full_name},\n\n"
                        f"You have been set as the host for a new meeting.\n\n"
                        f"Meeting: {meeting.title}\n"
                        f"Venue: {meeting.get_meeting_venue_display()}\n"
                        f"From: {meeting.from_datetime}\n"
                        f"To: {meeting.to_datetime}\n\n"
                        f"Please log in to the CRM to view the meeting details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify host for meeting %s", meeting.id)

        return HttpResponse("Meeting created successfully", status=201)

    except Exception as e:
        print("ADD MEETING ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_meetings(request):
    meetings = (
        Meeting.objects.filter(company=request.company)
        .select_related("host", "related_lead", "related_customer", "related_account")
        .prefetch_related("participants")
        .order_by("-created_at")
    )

    data = []
    for m in meetings:
        data.append({
            "id": m.id,
            "title": m.title,
            "meetingVenue": m.meeting_venue,
            "provider": m.provider,
            "location": m.location,
            "allDay": m.all_day,
            "fromDatetime": m.from_datetime.isoformat(),
            "toDatetime": m.to_datetime.isoformat(),
            "host": m.host.full_name if m.host else "—",
            "hostId": m.host.id if m.host else None,
            "participants": [{"id": p.id, "fullName": p.full_name} for p in m.participants.all()],
            "relatedType": m.related_type,
            "relatedLead": {"id": m.related_lead.id, "name": m.related_lead.full_name} if m.related_lead else None,
            "relatedCustomer": {"id": m.related_customer.id, "name": m.related_customer.company_name} if m.related_customer else None,
            "relatedAccount": {"id": m.related_account.id, "name": m.related_account.account_name} if m.related_account else None,
            "repeat": m.repeat,
            "createdAt": m.created_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_meeting(request, id):
    meeting = get_object_or_404(
        Meeting.objects.select_related(
            "host", "related_lead", "related_customer", "related_account"
        ).prefetch_related("participants"),
        id=id, company=request.company
    )

    data = {
        "id": meeting.id,
        "title": meeting.title,
        "meetingVenue": meeting.meeting_venue,
        "provider": meeting.provider,
        "location": meeting.location,
        "allDay": meeting.all_day,
        "fromDatetime": meeting.from_datetime.isoformat(),
        "toDatetime": meeting.to_datetime.isoformat(),
        "host": meeting.host.full_name if meeting.host else "—",
        "hostId": meeting.host.id if meeting.host else None,
        "participants": [{"id": p.id, "fullName": p.full_name} for p in meeting.participants.all()],
        "relatedType": meeting.related_type,
        "relatedLead": {"id": meeting.related_lead.id, "name": meeting.related_lead.full_name} if meeting.related_lead else None,
        "relatedCustomer": {"id": meeting.related_customer.id, "name": meeting.related_customer.company_name} if meeting.related_customer else None,
        "relatedAccount": {"id": meeting.related_account.id, "name": meeting.related_account.account_name} if meeting.related_account else None,
        "repeat": meeting.repeat,
        "createdAt": meeting.created_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_meeting(request, id):
    try:
        meeting = Meeting.objects.get(id=id, company=request.company)
    except Meeting.DoesNotExist:
        return HttpResponse("Meeting not found", status=404)

    previous_host_id = meeting.host_id

    try:
        meeting.title = request.data.get("title") or meeting.title
        meeting.meeting_venue = request.data.get("meeting_venue") or meeting.meeting_venue
        meeting.repeat = request.data.get("repeat") or meeting.repeat

        venue = meeting.meeting_venue
        if venue == "online":
            meeting.provider = request.data.get("provider") or meeting.provider
            meeting.location = ""
            meeting.all_day = False
        else:
            meeting.location = request.data.get("location") or meeting.location
            meeting.all_day = request.data.get("all_day", meeting.all_day)
            meeting.provider = ""

        from_datetime = request.data.get("from_datetime")
        if from_datetime:
            meeting.from_datetime = from_datetime

        to_datetime = request.data.get("to_datetime")
        if to_datetime:
            meeting.to_datetime = to_datetime

        host_id = request.data.get("host")
        if host_id:
            meeting.host_id = host_id
        else:
            meeting.host = None

        related_type = request.data.get("related_type")
        if related_type:
            meeting.related_type = related_type
            if related_type == "lead":
                meeting.related_lead_id = request.data.get("related_lead") or None
                meeting.related_customer = None
                meeting.related_account = None
            elif related_type == "customer":
                meeting.related_customer_id = request.data.get("related_customer") or None
                meeting.related_lead = None
                meeting.related_account = None
            elif related_type == "account":
                meeting.related_account_id = request.data.get("related_account") or None
                meeting.related_lead = None
                meeting.related_customer = None
            else:
                meeting.related_lead = None
                meeting.related_customer = None
                meeting.related_account = None

        meeting.save()

        participant_ids = request.data.get("participants")
        if participant_ids is not None:
            meeting.participants.set(participant_ids)

        if meeting.host and meeting.host_id != previous_host_id and meeting.host.user:
            try:
                notify_user(
                    company=request.company,
                    user=meeting.host.user,
                    notification_type="meeting_reminder",
                    title="You've Been Set as Meeting Host",
                    message=(
                        f"Hello {meeting.host.full_name},\n\n"
                        f"You have been set as the host for a meeting.\n\n"
                        f"Meeting: {meeting.title}\n"
                        f"From: {meeting.from_datetime}\n"
                        f"To: {meeting.to_datetime}\n\n"
                        f"Please log in to the CRM to view the meeting details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify host for updated meeting %s", meeting.id)

        return HttpResponse("Meeting updated successfully", status=200)

    except Exception as e:
        print("UPDATE MEETING ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_meeting(request, id):
    try:
        meeting = Meeting.objects.get(id=id, company=request.company)
        meeting.delete()
        return JsonResponse({"message": "Meeting deleted successfully"})
    except Meeting.DoesNotExist:
        return HttpResponse("Meeting not found", status=404)
    


# ................ calls ....................
@api_view(['POST'])
def add_call(request):
    subject = request.data.get("subject")
    call_type = request.data.get("call_type")
    status = request.data.get("status", "scheduled")
    start_time = request.data.get("start_time")
    duration = request.data.get("duration")
    notes = request.data.get("notes", "")
    assigned_to_id = request.data.get("assigned_to")
    related_type = request.data.get("related_type", "none")
    related_lead_id = request.data.get("related_lead")
    related_contact_id = request.data.get("related_contact")
    related_deal_id = request.data.get("related_deal")
    related_account_id = request.data.get("related_account")

    if not subject or not call_type or not start_time or not duration:
        return HttpResponse("Subject, call_type, start_time and duration are required", status=400)

    try:
        call = Call.objects.create(
            company=request.company,
            subject=subject,
            call_type=call_type,
            status=status,
            start_time=start_time,
            duration=duration,
            notes=notes,
            assigned_to_id=assigned_to_id or None,
            lead_id=related_lead_id if related_type == "lead" else None,
            contact_id=related_contact_id if related_type == "contact" else None,
            deal_id=related_deal_id if related_type == "deal" else None,
            account_id=related_account_id if related_type == "account" else None,
        )

        if call.assigned_to and call.assigned_to.user:
            related_label = get_related_label(related_type, call.lead, call.contact, call.deal, call.account)
            try:
                notify_user(
                    company=request.company,
                    user=call.assigned_to.user,
                    notification_type="call_assigned",
                    title="New Call Assigned",
                    message=(
                        f"Hello {call.assigned_to.full_name},\n\n"
                        f"A new call has been assigned to you.\n\n"
                        f"Call: {call.subject}\n"
                        f"Type: {call.call_type}\n"
                        f"Start Time: {call.start_time}\n"
                        + (f"Related To: {related_label}\n" if related_label else "")
                        + "\nPlease log in to the CRM to view the call details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for call %s", call.id)

        return HttpResponse("Call created successfully", status=201)

    except Exception as e:
        print("ADD CALL ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_calls(request):
    calls = (
        Call.objects.filter(company=request.company)
        .select_related("assigned_to", "lead", "contact", "deal", "account")
        .order_by("-start_time")
    )

    data = []
    for c in calls:
        data.append({
            "id": c.id,
            "subject": c.subject,
            "callType": c.call_type,
            "status": c.status,
            "startTime": c.start_time.isoformat(),
            "duration": c.duration,
            "notes": c.notes,
            "assignedTo": c.assigned_to.full_name if c.assigned_to else "—",
            "assignedToId": c.assigned_to.id if c.assigned_to else None,
            "relatedType": "lead" if c.lead else "contact" if c.contact else "deal" if c.deal else "account" if c.account else "none",
            "relatedLead": {"id": c.lead.id, "name": c.lead.full_name} if c.lead else None,
            "relatedContact": {"id": c.contact.id, "name": c.contact.company_name} if c.contact else None,
            "relatedDeal": {"id": c.deal.id, "name": c.deal.deal_name} if c.deal else None,
            "relatedAccount": {"id": c.account.id, "name": c.account.account_name} if c.account else None,
            "createdAt": c.created_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_call(request, id):
    call = get_object_or_404(
        Call.objects.select_related("assigned_to", "lead", "contact", "deal", "account"),
        id=id, company=request.company
    )

    data = {
        "id": call.id,
        "subject": call.subject,
        "callType": call.call_type,
        "status": call.status,
        "startTime": call.start_time.isoformat(),
        "duration": call.duration,
        "notes": call.notes,
        "assignedTo": call.assigned_to.full_name if call.assigned_to else "—",
        "assignedToId": call.assigned_to.id if call.assigned_to else None,
        "relatedType": "lead" if call.lead else "contact" if call.contact else "deal" if call.deal else "account" if call.account else "none",
        "relatedLead": {"id": call.lead.id, "name": call.lead.full_name} if call.lead else None,
        "relatedContact": {"id": call.contact.id, "name": call.contact.company_name} if call.contact else None,
        "relatedDeal": {"id": call.deal.id, "name": call.deal.deal_name} if call.deal else None,
        "relatedAccount": {"id": call.account.id, "name": call.account.account_name} if call.account else None,
        "createdAt": call.created_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_call(request, id):
    try:
        call = Call.objects.get(id=id, company=request.company)
    except Call.DoesNotExist:
        return HttpResponse("Call not found", status=404)

    previous_staff_id = call.assigned_to_id

    try:
        call.subject = request.data.get("subject") or call.subject
        call.call_type = request.data.get("call_type") or call.call_type
        call.status = request.data.get("status") or call.status
        call.notes = request.data.get("notes", call.notes)

        start_time = request.data.get("start_time")
        if start_time:
            call.start_time = start_time

        duration = request.data.get("duration")
        if duration:
            call.duration = duration

        assigned_to_id = request.data.get("assigned_to")
        if assigned_to_id:
            call.assigned_to_id = assigned_to_id
        else:
            call.assigned_to = None

        related_type = request.data.get("related_type")
        if related_type:
            call.lead = None
            call.contact = None
            call.deal = None
            call.account = None
            if related_type == "lead":
                call.lead_id = request.data.get("related_lead") or None
            elif related_type == "contact":
                call.contact_id = request.data.get("related_contact") or None
            elif related_type == "deal":
                call.deal_id = request.data.get("related_deal") or None
            elif related_type == "account":
                call.account_id = request.data.get("related_account") or None

        call.save()

        if call.assigned_to and call.assigned_to_id != previous_staff_id and call.assigned_to.user:
            related_type_resolved = "lead" if call.lead else "contact" if call.contact else "deal" if call.deal else "account" if call.account else "none"
            related_label = get_related_label(related_type_resolved, call.lead, call.contact, call.deal, call.account)
            try:
                notify_user(
                    company=request.company,
                    user=call.assigned_to.user,
                    notification_type="call_assigned",
                    title="Call Assigned to You",
                    message=(
                        f"Hello {call.assigned_to.full_name},\n\n"
                        f"A call has been reassigned to you.\n\n"
                        f"Call: {call.subject}\n"
                        f"Type: {call.call_type}\n"
                        f"Start Time: {call.start_time}\n"
                        + (f"Related To: {related_label}\n" if related_label else "")
                        + "\nPlease log in to the CRM to view the call details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned call %s", call.id)

        return HttpResponse("Call updated successfully", status=200)

    except Exception as e:
        print("UPDATE CALL ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_call(request, id):
    try:
        call = Call.objects.get(id=id, company=request.company)
        call.delete()
        return JsonResponse({"message": "Call deleted successfully"})
    except Call.DoesNotExist:
        return HttpResponse("Call not found", status=404)
    


# .............. vendor ................
@api_view(['GET'])
def get_vendor_prefill(request, vendor_id):
    """Fetch vendor address to prefill purchase order form"""
    vendor = get_object_or_404(Vendor, id=vendor_id, company=request.company)
    return JsonResponse({
        "vendorName": vendor.vendor_name,
        "billingAddress": _format_address(vendor.address),
    })


@api_view(['POST'])
def add_vendor(request):
    vendor_name = request.data.get("vendor_name")
    vendor_code = request.data.get("vendor_code")
    contact_person = request.data.get("contact_person", "")
    email = request.data.get("email", "")
    phone = request.data.get("phone", "")
    mobile = request.data.get("mobile", "")
    website = request.data.get("website", "")
    gst_number = request.data.get("gst_number", "")
    status = request.data.get("status", "active")
    notes = request.data.get("notes", "")
    address_data = request.data.get("address")

    if not vendor_name or not vendor_code:
        return HttpResponse("Vendor name and vendor code are required", status=400)

    if Vendor.objects.filter(vendor_code=vendor_code).exists():
        return HttpResponse("Vendor code already exists", status=400)

    try:
        address = _create_address(address_data) if address_data else None

        Vendor.objects.create(
            company=request.company,
            vendor_name=vendor_name,
            vendor_code=vendor_code,
            contact_person=contact_person,
            email=email,
            phone=phone,
            mobile=mobile,
            website=website,
            gst_number=gst_number,
            status=status,
            notes=notes,
            address=address,
        )
        return HttpResponse("Vendor created successfully", status=201)

    except Exception as e:
        print("ADD VENDOR ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_vendors(request):
    vendors = (
        Vendor.objects.filter(company=request.company)
        .select_related("address")
        .order_by("-updated_at")
    )

    data = []
    for v in vendors:
        data.append({
            "id": v.id,
            "vendorName": v.vendor_name,
            "vendorCode": v.vendor_code,
            "contactPerson": v.contact_person,
            "email": v.email,
            "phone": v.phone,
            "mobile": v.mobile,
            "website": v.website,
            "gstNumber": v.gst_number,
            "status": v.status,
            "notes": v.notes,
            "address": _format_address(v.address),
            "createdAt": v.created_at.isoformat(),
            "updatedAt": v.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_vendor(request, id):
    vendor = get_object_or_404(Vendor.objects.select_related("address"), id=id, company=request.company)

    data = {
        "id": vendor.id,
        "vendorName": vendor.vendor_name,
        "vendorCode": vendor.vendor_code,
        "contactPerson": vendor.contact_person,
        "email": vendor.email,
        "phone": vendor.phone,
        "mobile": vendor.mobile,
        "website": vendor.website,
        "gstNumber": vendor.gst_number,
        "status": vendor.status,
        "notes": vendor.notes,
        "address": _format_address(vendor.address),
        "createdAt": vendor.created_at.isoformat(),
        "updatedAt": vendor.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_vendor(request, id):
    try:
        vendor = Vendor.objects.select_related("address").get(id=id, company=request.company)
    except Vendor.DoesNotExist:
        return HttpResponse("Vendor not found", status=404)

    try:
        vendor.vendor_name = request.data.get("vendor_name") or vendor.vendor_name
        vendor.contact_person = request.data.get("contact_person", vendor.contact_person)
        vendor.email = request.data.get("email", vendor.email)
        vendor.phone = request.data.get("phone", vendor.phone)
        vendor.mobile = request.data.get("mobile", vendor.mobile)
        vendor.website = request.data.get("website", vendor.website)
        vendor.gst_number = request.data.get("gst_number", vendor.gst_number)
        vendor.status = request.data.get("status", vendor.status)
        vendor.notes = request.data.get("notes", vendor.notes)

        # vendor_code — only update if different
        new_code = request.data.get("vendor_code")
        if new_code and new_code != vendor.vendor_code:
            if Vendor.objects.filter(vendor_code=new_code).exists():
                return HttpResponse("Vendor code already exists", status=400)
            vendor.vendor_code = new_code

        # Update address
        address_data = request.data.get("address")
        if address_data:
            if vendor.address:
                vendor.address.country = address_data.get("country", vendor.address.country)
                vendor.address.address = address_data.get("address", vendor.address.address)
                vendor.address.street_address = address_data.get("street_add", vendor.address.street_address)
                vendor.address.city = address_data.get("city", vendor.address.city)
                vendor.address.state = address_data.get("state", vendor.address.state)
                vendor.address.zip_code = address_data.get("zip_code", vendor.address.zip_code)
                vendor.address.save()
            else:
                vendor.address = _create_address(address_data)

        vendor.save()
        return HttpResponse("Vendor updated successfully", status=200)

    except Exception as e:
        print("UPDATE VENDOR ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_vendor(request, id):
    try:
        vendor = Vendor.objects.get(id=id, company=request.company)
        vendor.delete()
        return JsonResponse({"message": "Vendor deleted successfully"})
    except Vendor.DoesNotExist:
        return HttpResponse("Vendor not found", status=404)
    

# .............. products ................


@api_view(['POST'])
def add_product(request):
    name = request.data.get("name")
    product_code = request.data.get("product_code")
    sku = request.data.get("sku")
    product_type = request.data.get("product_type", "goods")
    category = request.data.get("category", "")
    manufacturer = request.data.get("manufacturer", "")
    vendor_id = request.data.get("vendor_id")
    unit_price = request.data.get("unit_price")
    cost_price = request.data.get("cost_price", 0)
    tax_percentage = request.data.get("tax_percentage", 0)
    quantity_in_stock = request.data.get("quantity_in_stock", 0)
    reorder_level = request.data.get("reorder_level", 0)
    unit = request.data.get("unit", "Nos")
    description = request.data.get("description", "")
    status = request.data.get("status", "active")

    if not name or not product_code or not sku or not unit_price:
        return HttpResponse("Name, product_code, sku and unit_price are required", status=400)

    if Product.objects.filter(product_code=product_code).exists():
        return HttpResponse("Product code already exists", status=400)

    if Product.objects.filter(sku=sku).exists():
        return HttpResponse("SKU already exists", status=400)

    try:
        Product.objects.create(
            company=request.company,
            name=name,
            product_code=product_code,
            sku=sku,
            product_type=product_type,
            category=category,
            manufacturer=manufacturer,
            vendor_id=vendor_id or None,
            unit_price=unit_price,
            cost_price=cost_price,
            tax_percentage=tax_percentage,
            quantity_in_stock=quantity_in_stock,
            reorder_level=reorder_level,
            unit=unit,
            description=description,
            status=status,
        )
        return HttpResponse("Product created successfully", status=201)

    except Exception as e:
        print("ADD PRODUCT ERROR:", str(e))
        return HttpResponse(str(e), status=500)



@api_view(['GET'])
def view_products(request):
    products = ( 
        Product.objects.filter(company=request.company)
        .select_related("vendor")
    )

    data = []
    for p in products:
        data.append({
            "id": p.id,
            "name": p.name,
            "productCode": p.product_code,
            "sku": p.sku,
            "productType": p.product_type,
            "category": p.category,
            "manufacturer": p.manufacturer,
            "vendor": p.vendor.vendor_name if p.vendor else "—",
            "vendorId": p.vendor.id if p.vendor else None,
            "unitPrice": float(p.unit_price),
            "costPrice": float(p.cost_price),
            "taxPercentage": float(p.tax_percentage),
            "quantityInStock": p.quantity_in_stock,
            "reorderLevel": p.reorder_level,
            "unit": p.unit,
            "description": p.description,
            "status": p.status,
            "createdAt": p.created_at.isoformat(),
            "updatedAt": p.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_product(request, id):
    product = get_object_or_404(Product.objects.select_related("vendor"), id=id, company=request.company)

    data = {
        "id": product.id,
        "name": product.name,
        "productCode": product.product_code,
        "sku": product.sku,
        "productType": product.product_type,
        "category": product.category,
        "manufacturer": product.manufacturer,
        "vendor": product.vendor.vendor_name if product.vendor else "—",
        "vendorId": product.vendor.id if product.vendor else None,
        "unitPrice": float(product.unit_price),
        "costPrice": float(product.cost_price),
        "taxPercentage": float(product.tax_percentage),
        "quantityInStock": product.quantity_in_stock,
        "reorderLevel": product.reorder_level,
        "unit": product.unit,
        "description": product.description,
        "status": product.status,
        "createdAt": product.created_at.isoformat(),
        "updatedAt": product.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_product(request, id):
    try:
        product = Product.objects.get(id=id, company=request.company)
    except Product.DoesNotExist:
        return HttpResponse("Product not found", status=404)

    try:
        product.name = request.data.get("name") or product.name
        product.product_type = request.data.get("product_type", product.product_type)
        product.category = request.data.get("category", product.category)
        product.manufacturer = request.data.get("manufacturer", product.manufacturer)
        product.unit_price = request.data.get("unit_price") or product.unit_price
        product.cost_price = request.data.get("cost_price", product.cost_price)
        product.tax_percentage = request.data.get("tax_percentage", product.tax_percentage)
        product.quantity_in_stock = request.data.get("quantity_in_stock", product.quantity_in_stock)
        product.reorder_level = request.data.get("reorder_level", product.reorder_level)
        product.unit = request.data.get("unit", product.unit)
        product.description = request.data.get("description", product.description)
        product.status = request.data.get("status", product.status)

        vendor_id = request.data.get("vendor_id")
        if vendor_id:
            product.vendor_id = vendor_id
        elif vendor_id == "":
            product.vendor = None

        # product_code — only update if different
        new_code = request.data.get("product_code")
        if new_code and new_code != product.product_code:
            if Product.objects.filter(product_code=new_code).exists():
                return HttpResponse("Product code already exists", status=400)
            product.product_code = new_code

        # sku — only update if different
        new_sku = request.data.get("sku")
        if new_sku and new_sku != product.sku:
            if Product.objects.filter(sku=new_sku).exists():
                return HttpResponse("SKU already exists", status=400)
            product.sku = new_sku

        product.save()
        return HttpResponse("Product updated successfully", status=200)

    except Exception as e:
        print("UPDATE PRODUCT ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_product(request, id):
    try:
        product = Product.objects.get(id=id, company=request.company)
        product.delete()
        return JsonResponse({"message": "Product deleted successfully"})
    except Product.DoesNotExist:
        return HttpResponse("Product not found", status=404)
    


# ---------------- PRICE BOOK ----------------
@api_view(['POST'])
def add_price_book(request):
    name = request.data.get("name")
    description = request.data.get("description", "")
    status = request.data.get("status", "active")

    if not name:
        return HttpResponse("Name is required", status=400)

    if PriceBook.objects.filter(name=name).exists():
        return HttpResponse("Price book name already exists", status=400)

    try:
        PriceBook.objects.create(
            name=name,
            description=description,
            status=status,
        )
        return HttpResponse("Price book created successfully", status=201)

    except Exception as e:
        print("ADD PRICE BOOK ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_price_books(request):
    price_books = PriceBook.objects.all()

    data = []
    for pb in price_books:
        data.append({
            "id": pb.id,
            "name": pb.name,
            "description": pb.description,
            "status": pb.status,
            "itemCount": pb.items.count(),
            "createdAt": pb.created_at.isoformat(),
            "updatedAt": pb.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_price_book(request, id):
    price_book = get_object_or_404(PriceBook, id=id)

    items = []
    for item in price_book.items.select_related("product").all():
        items.append({
            "id": item.id,
            "productId": item.product.id,
            "productName": item.product.name,
            "productCode": item.product.product_code,
            "price": float(item.price),
        })

    data = {
        "id": price_book.id,
        "name": price_book.name,
        "description": price_book.description,
        "status": price_book.status,
        "items": items,
        "createdAt": price_book.created_at.isoformat(),
        "updatedAt": price_book.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_price_book(request, id):
    try:
        price_book = PriceBook.objects.get(id=id, company=request.company)
    except PriceBook.DoesNotExist:
        return HttpResponse("Price book not found", status=404)

    try:
        new_name = request.data.get("name")
        if new_name and new_name != price_book.name:
            if PriceBook.objects.filter(name=new_name).exists():
                return HttpResponse("Price book name already exists", status=400)
            price_book.name = new_name

        price_book.description = request.data.get("description", price_book.description)
        price_book.status = request.data.get("status", price_book.status)

        price_book.save()
        return HttpResponse("Price book updated successfully", status=200)

    except Exception as e:
        print("UPDATE PRICE BOOK ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_price_book(request, id):
    try:
        price_book = PriceBook.objects.get(id=id, company=request.company)
        price_book.delete()
        return JsonResponse({"message": "Price book deleted successfully"})
    except PriceBook.DoesNotExist:
        return HttpResponse("Price book not found", status=404)


# ---------------- PRICE BOOK ITEM ----------------
@api_view(['POST'])
def add_price_book_item(request):
    price_book_id = request.data.get("price_book_id")
    product_id = request.data.get("product_id")
    price = request.data.get("price")

    if not price_book_id or not product_id or price is None:
        return HttpResponse("price_book_id, product_id and price are required", status=400)

    price_book = get_object_or_404(PriceBook, id=price_book_id)
    product = get_object_or_404(Product, id=product_id)

    if PriceBookItem.objects.filter(price_book=price_book, product=product).exists():
        return HttpResponse("This product already exists in the price book", status=400)

    try:
        PriceBookItem.objects.create(
            price_book=price_book,
            product=product,
            price=price,
        )
        return HttpResponse("Price book item created successfully", status=201)

    except Exception as e:
        print("ADD PRICE BOOK ITEM ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_price_book_items(request):
    items = PriceBookItem.objects.select_related("price_book", "product").all()

    price_book_id = request.query_params.get("price_book_id")
    if price_book_id:
        items = items.filter(price_book_id=price_book_id)

    data = []
    for item in items:
        data.append({
            "id": item.id,
            "priceBookId": item.price_book.id,
            "priceBookName": item.price_book.name,
            "productId": item.product.id,
            "productName": item.product.name,
            "productCode": item.product.product_code,
            "price": float(item.price),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_price_book_item(request, id):
    item = get_object_or_404(PriceBookItem.objects.select_related("price_book", "product"), id=id)

    data = {
        "id": item.id,
        "priceBookId": item.price_book.id,
        "priceBookName": item.price_book.name,
        "productId": item.product.id,
        "productName": item.product.name,
        "productCode": item.product.product_code,
        "price": float(item.price),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_price_book_item(request, id):
    try:
        item = PriceBookItem.objects.get(id=id, company=request.company)
    except PriceBookItem.DoesNotExist:
        return HttpResponse("Price book item not found", status=404)

    try:
        new_product_id = request.data.get("product_id")
        if new_product_id and int(new_product_id) != item.product_id:
            product = get_object_or_404(Product, id=new_product_id)
            if PriceBookItem.objects.filter(price_book=item.price_book, product=product).exists():
                return HttpResponse("This product already exists in the price book", status=400)
            item.product = product

        price = request.data.get("price")
        if price is not None:
            item.price = price

        item.save()
        return HttpResponse("Price book item updated successfully", status=200)

    except Exception as e:
        print("UPDATE PRICE BOOK ITEM ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_price_book_item(request, id):
    try:
        item = PriceBookItem.objects.get(id=id, company=request.company)
        item.delete()
        return JsonResponse({"message": "Price book item deleted successfully"})
    except PriceBookItem.DoesNotExist:
        return HttpResponse("Price book item not found", status=404)
    


# .............. seles orders and item ...............
def _format_address(address):
    if not address:
        return None
    return {
        "country": address.country,
        "address": address.address,
        "streetAddress": address.street_address,
        "city": address.city,
        "state": address.state,
        "zipCode": address.zip_code,
    }

def _create_address(data):
    if not data:
        return None
    return Address.objects.create(
        country=data.get("country", ""),
        address=data.get("address", ""),
        street_address=data.get("street_add", ""),
        city=data.get("city", ""),
        state=data.get("state", ""),
        zip_code=data.get("zip_code", ""),
    )

def _update_address(existing, data):
    if not data:
        return existing
    if existing:
        existing.country = data.get("country", existing.country)
        existing.address = data.get("address", existing.address)
        existing.street_address = data.get("street_add", existing.street_address)
        existing.city = data.get("city", existing.city)
        existing.state = data.get("state", existing.state)
        existing.zip_code = data.get("zip_code", existing.zip_code)
        existing.save()
        return existing
    return _create_address(data)


@api_view(['GET'])
def get_quote_prefill(request, quote_id):
    quote = get_object_or_404(
        Quotes.objects.select_related(
            "assigned_to",
            "deal",
            "account",
            "billing_address",
            "shipping_address",
        ).prefetch_related("items__product", "items__service"),
        id=quote_id,
        company=request.company,
    )

    items = []

    for item in quote.items.all():
        items.append({
            "productId": item.product.id if item.product else None,
            "productName": item.product.name if item.product else "",
            "serviceId": item.service.id if item.service else None,
            "serviceName": item.service.name if item.service else "",
            "description": item.description,
            "quantity": item.quantity,
            "listPrice": float(item.list_price),
            "discount": float(item.discount),
            "tax": float(item.tax),
            "amount": float(item.amount),
            "total": float(item.total),
        })

    return JsonResponse({
        "subject": quote.subject,
        "contactName": quote.contact_name,

        "accountId": quote.account.id if quote.account else None,
        "accountName": quote.account.company_name if quote.account else "",

        "customerId": quote.customer.id if quote.customer else None,
        "customerName": quote.customer.company_name if quote.customer else "",

        "dealId": quote.deal.id if quote.deal else None,
        "dealName": quote.deal.deal_name if quote.deal else "",

        "billingAddress": _format_address(quote.billing_address),
        "shippingAddress": _format_address(quote.shipping_address),
        "items": items,
    })


@api_view(['POST'])
def add_sales_order(request):
    subject = request.data.get("subject")
    customer_id = request.data.get("customer_id")
    owner_id = request.data.get("owner_id")
    quote_id = request.data.get("quote_id")
    deal_id = request.data.get("deal_id")
    purchase_order_number = request.data.get("purchase_order_number", "")
    carrier = request.data.get("carrier", "")
    sales_commission = request.data.get("sales_commission", 0)
    due_date = request.data.get("due_date")
    status = request.data.get("status", "created")
    excise_duty = request.data.get("excise_duty", 0)
    terms_and_conditions = request.data.get("terms_and_conditions", "")
    description = request.data.get("description", "")
    billing_data = request.data.get("billing_add")
    shipping_data = request.data.get("shipping_add")
    items_data = request.data.get("items", [])

    if not subject or not customer_id:
        return HttpResponse("Subject and customer are required", status=400)

    try:
        billing_address = None
        shipping_address = None
        quote = None

        if quote_id:
            try:
                quote = Quotes.objects.select_related(
                    "billing_address", "shipping_address"
                ).prefetch_related("items").get(id=quote_id)
            except Quotes.DoesNotExist:
                quote = None

        if quote and not billing_data and not shipping_data:
            if quote.billing_address:
                billing_address = Address.objects.create(
                    country=quote.billing_address.country,
                    address=quote.billing_address.address,
                    street_address=quote.billing_address.street_address,
                    city=quote.billing_address.city,
                    state=quote.billing_address.state,
                    zip_code=quote.billing_address.zip_code,
                )
            if quote.shipping_address:
                shipping_address = Address.objects.create(
                    country=quote.shipping_address.country,
                    address=quote.shipping_address.address,
                    street_address=quote.shipping_address.street_address,
                    city=quote.shipping_address.city,
                    state=quote.shipping_address.state,
                    zip_code=quote.shipping_address.zip_code,
                )
        else:
            billing_address = _create_address(billing_data)
            shipping_address = _create_address(shipping_data)

        if quote and not deal_id:
            deal_id = quote.deal_id

        sales_order = SalesOrder.objects.create(
            company=request.company,
            subject=subject,
            customer_id=customer_id,
            owner_id=owner_id or None,
            quote_id=quote_id or None,
            deal_id=deal_id or None,
            purchase_order_number=purchase_order_number,
            carrier=carrier,
            sales_commission=sales_commission,
            due_date=due_date or None,
            status=status,
            excise_duty=excise_duty,
            billing_address=billing_address,
            shipping_address=shipping_address,
            terms_and_conditions=terms_and_conditions,
            description=description,
        )

        if not items_data and quote:
            items_data = [
                {
                    "product_id": qi.product_id,
                    "quantity": qi.quantity,
                    "list_price": qi.list_price,
                    "discount": qi.discount,
                    "tax": qi.tax,
                    "description": qi.description,
                }
                for qi in quote.items.all()
            ]

        for item in items_data:
            quantity = int(item.get("quantity", 1))
            list_price = float(item.get("list_price", 0))
            discount = float(item.get("discount", 0))
            tax = float(item.get("tax", 0))

            SalesOrderItem.objects.create(
                sales_order=sales_order,
                product_id=item.get("product_id"),
                quantity=quantity,
                list_price=list_price,
                discount=discount,
                tax=tax,
                description=item.get("description", ""),
            )

        if sales_order.owner and sales_order.owner.user:
            try:
                notify_user(
                    company=request.company,
                    user=sales_order.owner.user,
                    notification_type="sales_order",
                    title="New Sales Order Assigned",
                    message=(
                        f"Hello {sales_order.owner.full_name},\n\n"
                        f"A new sales order has been assigned to you.\n\n"
                        f"Sales Order: {sales_order.subject}\n"
                        f"Customer: {sales_order.customer.company_name}\n"
                        f"Status: {sales_order.status}\n\n"
                        f"Please log in to the CRM to view the sales order details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for sales order %s", sales_order.id)

        return HttpResponse("Sales order created successfully", status=201)

    except Exception as e:
        print("ADD SALES ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_sales_orders(request):
    orders = (
        SalesOrder.objects.filter(company=request.company)
        .select_related(
            "owner",
            "customer",
            "quote",
            "deal",
            "billing_address",
            "shipping_address",
        )
        .prefetch_related("items__product")
        .order_by("-updated_at")
    )

    data = []
    for o in orders:
        data.append({
            "id": o.id,
            "subject": o.subject,
            "status": o.status,
            "owner": o.owner.full_name if o.owner else "—",
            "ownerId": o.owner.id if o.owner else None,
            "customer": o.customer.company_name,
            "customerId": o.customer.id,
            "quote": o.quote.subject if o.quote else "—",
            "quoteId": o.quote.id if o.quote else None,
            "deal": o.deal.deal_name if o.deal else "—",
            "dealId": o.deal.id if o.deal else None,
            "purchaseOrderNumber": o.purchase_order_number,
            "carrier": o.carrier,
            "salesCommission": float(o.sales_commission),
            "dueDate": str(o.due_date) if o.due_date else None,
            "exciseDuty": float(o.excise_duty),
            "billingAddress": _format_address(o.billing_address),
            "shippingAddress": _format_address(o.shipping_address),
            "termsAndConditions": o.terms_and_conditions,
            "description": o.description,
            "items": [
                {
                    "id": item.id,
                    "productId": item.product.id,
                    "productName": item.product.name,
                    "quantity": item.quantity,
                    "listPrice": float(item.list_price),
                    "discount": float(item.discount),
                    "tax": float(item.tax),
                    "lineTotal": float(item.line_total),
                    "description": item.description,
                }
                for item in o.items.all()
            ],
            "createdAt": o.created_at.isoformat(),
            "updatedAt": o.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_sales_order(request, id):
    order = get_object_or_404(
        SalesOrder.objects.select_related("owner", "customer", "quote", "deal", "billing_address", "shipping_address").prefetch_related("items__product"),
        id=id, company=request.company
    )

    data = {
        "id": order.id,
        "subject": order.subject,
        "status": order.status,
        "owner": order.owner.full_name if order.owner else "—",
        "ownerId": order.owner.id if order.owner else None,
        "customer": order.customer.company_name,
        "customerId": order.customer.id,
        "quote": order.quote.subject if order.quote else "—",
        "quoteId": order.quote.id if order.quote else None,
        "deal": order.deal.deal_name if order.deal else "—",
        "dealId": order.deal.id if order.deal else None,
        "purchaseOrderNumber": order.purchase_order_number,
        "carrier": order.carrier,
        "salesCommission": float(order.sales_commission),
        "dueDate": str(order.due_date) if order.due_date else None,
        "exciseDuty": float(order.excise_duty),
        "billingAddress": _format_address(order.billing_address),
        "shippingAddress": _format_address(order.shipping_address),
        "termsAndConditions": order.terms_and_conditions,
        "description": order.description,
        "items": [
            {
                "id": item.id,
                "productId": item.product.id,
                "productName": item.product.name,
                "quantity": item.quantity,
                "listPrice": float(item.list_price),
                "discount": float(item.discount),
                "tax": float(item.tax),
                "lineTotal": float(item.line_total),
                "description": item.description,
            }
            for item in order.items.all()
        ],
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_sales_order(request, id):
    try:
        order = SalesOrder.objects.get(id=id, company=request.company)
    except SalesOrder.DoesNotExist:
        return HttpResponse("Sales order not found", status=404)

    previous_owner_id = order.owner_id

    try:
        with transaction.atomic():
            order.subject = request.data.get("subject") or order.subject
            order.status = request.data.get("status", order.status)
            order.purchase_order_number = request.data.get("purchase_order_number", order.purchase_order_number)
            order.carrier = request.data.get("carrier", order.carrier)
            order.sales_commission = request.data.get("sales_commission", order.sales_commission)
            order.excise_duty = request.data.get("excise_duty", order.excise_duty)
            order.terms_and_conditions = request.data.get("terms_and_conditions", order.terms_and_conditions)
            order.description = request.data.get("description", order.description)

            due_date = request.data.get("due_date")
            if due_date:
                order.due_date = due_date

            owner_id = request.data.get("owner_id")
            if owner_id:
                order.owner_id = owner_id

            customer_id = request.data.get("customer_id")
            if customer_id:
                order.customer_id = customer_id

            quote_id = request.data.get("quote_id")
            if quote_id:
                order.quote_id = quote_id

            deal_id = request.data.get("deal_id")
            if deal_id:
                order.deal_id = deal_id

            billing_data = request.data.get("billing_add")
            order.billing_address = _update_address(order.billing_address, billing_data)

            shipping_data = request.data.get("shipping_add")
            order.shipping_address = _update_address(order.shipping_address, shipping_data)

            order.save()

            items_data = request.data.get("items")
            if items_data is not None:
                order.items.all().delete()
                for item in items_data:
                    quantity = int(item.get("quantity", 1))
                    list_price = float(item.get("list_price", 0))
                    discount = float(item.get("discount", 0))
                    tax = float(item.get("tax", 0))

                    SalesOrderItem.objects.create(
                        sales_order=order,
                        product_id=item.get("product_id"),
                        quantity=quantity,
                        list_price=list_price,
                        discount=discount,
                        tax=tax,
                        description=item.get("description", ""),
                    )

        if order.owner and order.owner_id != previous_owner_id and order.owner.user:
            try:
                notify_user(
                    company=request.company,
                    user=order.owner.user,
                    notification_type="sales_order",
                    title="Sales Order Assigned to You",
                    message=(
                        f"Hello {order.owner.full_name},\n\n"
                        f"A sales order has been reassigned to you.\n\n"
                        f"Sales Order: {order.subject}\n"
                        f"Customer: {order.customer.company_name}\n"
                        f"Status: {order.status}\n\n"
                        f"Please log in to the CRM to view the sales order details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned sales order %s", order.id)

        return HttpResponse("Sales order updated successfully", status=200)

    except Exception as e:
        print("UPDATE SALES ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_sales_order(request, id):
    try:
        order = SalesOrder.objects.get(id=id, company=request.company)
        order.delete()
        return JsonResponse({"message": "Sales order deleted successfully"})
    except SalesOrder.DoesNotExist:
        return HttpResponse("Sales order not found", status=404)
    


# ............... invioce .................
@api_view(['GET'])
def get_sales_order_prefill(request, sales_order_id):
    """Fetch sales order data to prefill invoice form"""
    order = get_object_or_404(
        SalesOrder.objects.select_related(
            "owner", "customer", "quote", "deal",
            "billing_address", "shipping_address"
        ).prefetch_related("items__product"),
        id=sales_order_id,
        company=request.company
    )

    return JsonResponse({
        "subject": order.subject,
        "customerId": order.customer.id,
        "customerName": order.customer.company_name,
        "dealId": order.deal.id if order.deal else None,
        "purchaseOrderNumber": order.purchase_order_number,
        "billingAddress": _format_address(order.billing_address),
        "shippingAddress": _format_address(order.shipping_address),
        "termsAndConditions": order.terms_and_conditions,
        "items": [
            {
                "productId": item.product.id,
                "productName": item.product.name,
                "quantity": item.quantity,
                "listPrice": float(item.list_price),
                "discount": float(item.discount),
                "tax": float(item.tax),
                "lineTotal": float(item.line_total),
                "description": item.description,
            }
            for item in order.items.all()
        ],
    })


@api_view(['POST'])
def add_invoice(request):
    subject = request.data.get("subject")
    customer_id = request.data.get("customer_id")
    owner_id = request.data.get("owner_id")
    sales_order_id = request.data.get("sales_order_id")
    invoice_date = request.data.get("invoice_date")
    due_date = request.data.get("due_date")
    purchase_order_number = request.data.get("purchase_order_number", "")
    status = request.data.get("status", "draft")
    terms_and_conditions = request.data.get("terms_and_conditions", "")
    description = request.data.get("description", "")
    billing_data = request.data.get("billing_add")
    shipping_data = request.data.get("shipping_add")
    items_data = request.data.get("items", [])

    if not subject or not customer_id or not invoice_date:
        return HttpResponse("Subject, customer and invoice_date are required", status=400)

    try:
        billing_address = None
        shipping_address = None

        if sales_order_id and not billing_data and not shipping_data:
            try:
                sales_order = SalesOrder.objects.select_related(
                    "billing_address", "shipping_address"
                ).prefetch_related("items__product").get(id=sales_order_id)

                if sales_order.billing_address:
                    billing_address = Address.objects.create(
                        country=sales_order.billing_address.country,
                        address=sales_order.billing_address.address,
                        street_address=sales_order.billing_address.street_address,
                        city=sales_order.billing_address.city,
                        state=sales_order.billing_address.state,
                        zip_code=sales_order.billing_address.zip_code,
                    )

                if sales_order.shipping_address:
                    shipping_address = Address.objects.create(
                        country=sales_order.shipping_address.country,
                        address=sales_order.shipping_address.address,
                        street_address=sales_order.shipping_address.street_address,
                        city=sales_order.shipping_address.city,
                        state=sales_order.shipping_address.state,
                        zip_code=sales_order.shipping_address.zip_code,
                    )

                if not items_data:
                    items_data = [
                        {
                            "product_id": item.product.id,
                            "quantity": item.quantity,
                            "list_price": float(item.list_price),
                            "discount": float(item.discount),
                            "tax": float(item.tax),
                            "description": item.description,
                        }
                        for item in sales_order.items.all()
                    ]

            except SalesOrder.DoesNotExist:
                pass
        else:
            billing_address = _create_address(billing_data)
            shipping_address = _create_address(shipping_data)

        invoice = Invoice.objects.create(
            company=request.company,
            subject=subject,
            customer_id=customer_id,
            owner_id=owner_id or None,
            sales_order_id=sales_order_id or None,
            invoice_date=invoice_date,
            due_date=due_date or None,
            purchase_order_number=purchase_order_number,
            status=status,
            billing_address=billing_address,
            shipping_address=shipping_address,
            terms_and_conditions=terms_and_conditions,
            description=description,
        )

        for item in items_data:
            InvoiceItem.objects.create(
                invoice=invoice,
                product_id=item.get("product_id"),
                quantity=int(item.get("quantity", 1)),
                list_price=float(item.get("list_price", 0)),
                discount=float(item.get("discount", 0)),
                tax=float(item.get("tax", 0)),
            )

        if invoice.owner and invoice.owner.user:
            try:
                notify_user(
                    company=request.company,
                    user=invoice.owner.user,
                    notification_type="invoice_created",
                    title="New Invoice Assigned",
                    message=(
                        f"Hello {invoice.owner.full_name},\n\n"
                        f"A new invoice has been assigned to you.\n\n"
                        f"Invoice: {invoice.invoice_number} - {invoice.subject}\n"
                        f"Customer: {invoice.customer.company_name}\n"
                        f"Status: {invoice.status}\n\n"
                        f"Please log in to the CRM to view the invoice details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for invoice %s", invoice.id)

        return HttpResponse("Invoice created successfully", status=201)

    except Exception as e:
        print("ADD INVOICE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_invoices(request):
    invoices = (
        Invoice.objects.filter(company=request.company)
        .select_related(
            "owner",
            "customer",
            "sales_order",
            "billing_address",
            "shipping_address",
        )
        .prefetch_related("items__product")
        .order_by("-updated_at")
    )

    data = []
    for inv in invoices:
        data.append({
            "id": inv.id,
            "subject": inv.subject,
            "invoiceNumber": inv.invoice_number,
            "status": inv.status,
            "invoiceDate": str(inv.invoice_date),
            "dueDate": str(inv.due_date) if inv.due_date else None,
            "owner": inv.owner.full_name if inv.owner else "—",
            "ownerId": inv.owner.id if inv.owner else None,
            "customer": inv.customer.company_name,
            "customerId": inv.customer.id,
            "salesOrder": inv.sales_order.subject if inv.sales_order else "—",
            "salesOrderId": inv.sales_order.id if inv.sales_order else None,
            "purchaseOrderNumber": inv.purchase_order_number,
            "billingAddress": _format_address(inv.billing_address),
            "shippingAddress": _format_address(inv.shipping_address),
            "termsAndConditions": inv.terms_and_conditions,
            "description": inv.description,
            "items": [
                {
                    "id": item.id,
                    "productId": item.product.id,
                    "productName": item.product.name,
                    "quantity": item.quantity,
                    "listPrice": float(item.list_price),
                    "discount": float(item.discount),
                    "tax": float(item.tax),
                    "lineTotal": float(item.line_total),
                }
                for item in inv.items.all()
            ],
            "createdAt": inv.created_at.isoformat(),
            "updatedAt": inv.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_invoice(request, id):
    invoice = get_object_or_404(
        Invoice.objects.select_related("owner", "customer", "sales_order", "billing_address", "shipping_address").prefetch_related("items__product"),
        id=id, company=request.company
    )

    data = {
        "id": invoice.id,
        "subject": invoice.subject,
        "invoiceNumber": invoice.invoice_number,
        "status": invoice.status,
        "invoiceDate": str(invoice.invoice_date),
        "dueDate": str(invoice.due_date) if invoice.due_date else None,
        "owner": invoice.owner.full_name if invoice.owner else "—",
        "ownerId": invoice.owner.id if invoice.owner else None,
        "customer": invoice.customer.company_name,
        "customerId": invoice.customer.id,
        "salesOrder": invoice.sales_order.subject if invoice.sales_order else "—",
        "salesOrderId": invoice.sales_order.id if invoice.sales_order else None,
        "purchaseOrderNumber": invoice.purchase_order_number,
        "billingAddress": _format_address(invoice.billing_address),
        "shippingAddress": _format_address(invoice.shipping_address),
        "termsAndConditions": invoice.terms_and_conditions,
        "description": invoice.description,
        "items": [
            {
                "id": item.id,
                "productId": item.product.id,
                "productName": item.product.name,
                "quantity": item.quantity,
                "listPrice": float(item.list_price),
                "discount": float(item.discount),
                "tax": float(item.tax),
                "lineTotal": float(item.line_total),
            }
            for item in invoice.items.all()
        ],
        "createdAt": invoice.created_at.isoformat(),
        "updatedAt": invoice.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_invoice(request, id):
    try:
        invoice = Invoice.objects.get(id=id, company=request.company)
    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not found", status=404)

    previous_owner_id = invoice.owner_id

    try:
        invoice.subject = request.data.get("subject") or invoice.subject
        invoice.status = request.data.get("status", invoice.status)
        invoice.purchase_order_number = request.data.get("purchase_order_number", invoice.purchase_order_number)
        invoice.terms_and_conditions = request.data.get("terms_and_conditions", invoice.terms_and_conditions)
        invoice.description = request.data.get("description", invoice.description)

        invoice_date = request.data.get("invoice_date")
        if invoice_date:
            invoice.invoice_date = invoice_date

        due_date = request.data.get("due_date")
        if due_date:
            invoice.due_date = due_date

        owner_id = request.data.get("owner_id")
        if owner_id:
            invoice.owner_id = owner_id

        customer_id = request.data.get("customer_id")
        if customer_id:
            invoice.customer_id = customer_id

        sales_order_id = request.data.get("sales_order_id")
        if sales_order_id:
            invoice.sales_order_id = sales_order_id

        billing_data = request.data.get("billing_add")
        invoice.billing_address = _update_address(invoice.billing_address, billing_data)

        shipping_data = request.data.get("shipping_add")
        invoice.shipping_address = _update_address(invoice.shipping_address, shipping_data)

        invoice.save()

        items_data = request.data.get("items")
        if items_data is not None:
            invoice.items.all().delete()
            for item in items_data:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    product_id=item.get("product_id"),
                    quantity=int(item.get("quantity", 1)),
                    list_price=float(item.get("list_price", 0)),
                    discount=float(item.get("discount", 0)),
                    tax=float(item.get("tax", 0)),
                )

        if invoice.owner and invoice.owner_id != previous_owner_id and invoice.owner.user:
            try:
                notify_user(
                    company=request.company,
                    user=invoice.owner.user,
                    notification_type="invoice_created",
                    title="Invoice Assigned to You",
                    message=(
                        f"Hello {invoice.owner.full_name},\n\n"
                        f"An invoice has been reassigned to you.\n\n"
                        f"Invoice: {invoice.invoice_number} - {invoice.subject}\n"
                        f"Customer: {invoice.customer.company_name}\n"
                        f"Status: {invoice.status}\n\n"
                        f"Please log in to the CRM to view the invoice details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned invoice %s", invoice.id)

        return HttpResponse("Invoice updated successfully", status=200)

    except Exception as e:
        print("UPDATE INVOICE ERROR:", str(e))
        return HttpResponse(str(e), status=500)

@api_view(['DELETE'])
def delete_invoice(request, id):
    try:
        invoice = Invoice.objects.get(id=id, company=request.company)
        invoice.delete()
        return JsonResponse({"message": "Invoice deleted successfully"})
    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not found", status=404)


def _address_dict(address):
    if not address:
        return {"address": "", "street_address": "", "city": "", "state": "", "zip_code": "", "country": ""}
    return {
        "address": address.address or "",
        "street_address": getattr(address, "street_address", "") or "",
        "city": address.city or "",
        "state": address.state or "",
        "zip_code": address.zip_code or "",
        "country": address.country or "",
    }


@api_view(["GET"])
def invoice_pdf(request, pk):
    try:
        invoice = Invoice.objects.select_related(
            "customer", "billing_address", "shipping_address"
        ).prefetch_related("items__product").get(pk=pk, company=request.company)
    except Invoice.DoesNotExist:
        return Response({"detail": "Invoice not found."}, status=404)

    items_data = []
    sub_total = discount_total = tax_total = 0

    for item in invoice.items.all():
        amount = float(item.list_price) * item.quantity
        sub_total += amount
        discount_total += float(item.discount)
        tax_total += float(item.tax)
        items_data.append({
            "product_name": item.product.name if item.product else "",
            "quantity": item.quantity,
            "list_price": f"{item.list_price:.2f}",
            "discount": f"{item.discount:.2f}",
            "tax": f"{item.tax:.2f}",
            "line_total": f"{item.line_total:.2f}",
        })

    grand_total = sub_total - discount_total + tax_total

    html_string = render_to_string("invoice_pdf.html", {
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "subject": invoice.subject,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "purchase_order_number": invoice.purchase_order_number,
            "terms_and_conditions": invoice.terms_and_conditions,
            "customer_name": invoice.customer.company_name if invoice.customer else "",
        },
        "billing": _address_dict(invoice.billing_address),
        "items": items_data,
        "totals": {
            "sub_total": f"{sub_total:.2f}",
            "discount_total": f"{discount_total:.2f}",
            "tax_total": f"{tax_total:.2f}",
            "grand_total": f"{grand_total:.2f}",
        },
    })

    result = BytesIO()
    pdf = pisa.CreatePDF(src=html_string, dest=result)

    if pdf.err:
        return Response({"detail": "Failed to generate PDF."}, status=500)

    response = HttpResponse(result.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
    return response

# .............. purchase order ...............
@api_view(['POST'])
def add_purchase_order(request):
    subject = request.data.get("subject")
    vendor_id = request.data.get("vendor_id")
    owner_id = request.data.get("owner_id")
    purchase_date = request.data.get("purchase_date")
    expected_delivery_date = request.data.get("expected_delivery_date")
    status = request.data.get("status", "created")
    terms_and_conditions = request.data.get("terms_and_conditions", "")
    description = request.data.get("description", "")
    billing_data = request.data.get("billing_add")
    shipping_data = request.data.get("shipping_add")
    items_data = request.data.get("items", [])

    if not subject or not vendor_id or not purchase_date:
        return HttpResponse("Subject, vendor and purchase_date are required", status=400)

    try:
        # Auto-fill address from vendor if not provided
        billing_address = None
        shipping_address = None

        if not billing_data:
            try:
                vendor = Vendor.objects.select_related("address").get(id=vendor_id)
                if vendor.address:
                    billing_address = Address.objects.create(
                        country=vendor.address.country,
                        address=vendor.address.address,
                        street_address=vendor.address.street_address,
                        city=vendor.address.city,
                        state=vendor.address.state,
                        zip_code=vendor.address.zip_code,
                    )
            except Vendor.DoesNotExist:
                pass
        else:
            billing_address = _create_address(billing_data)

        if shipping_data:
            shipping_address = _create_address(shipping_data)

        purchase_order = PurchaseOrder.objects.create(
            company=request.company,
            subject=subject,
            vendor_id=vendor_id,
            owner_id=owner_id or None,
            purchase_date=purchase_date,
            expected_delivery_date=expected_delivery_date or None,
            status=status,
            billing_address=billing_address,
            shipping_address=shipping_address,
            terms_and_conditions=terms_and_conditions,
            description=description,
        )

        for item in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                product_id=item.get("product_id"),
                quantity=int(item.get("quantity", 1)),
                list_price=float(item.get("list_price", 0)),
                discount=float(item.get("discount", 0)),
                tax=float(item.get("tax", 0)),
                description=item.get("description", ""),
            )

        return HttpResponse("Purchase order created successfully", status=201)

    except Exception as e:
        print("ADD PURCHASE ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_purchase_orders(request):
    orders = (
        PurchaseOrder.objects.filter(company=request.company)
        .select_related(
            "owner",
            "vendor",
            "billing_address",
            "shipping_address",
        )
        .prefetch_related("items__product")
        .order_by("-updated_at")
    )

    data = []
    for o in orders:
        data.append({
            "id": o.id,
            "subject": o.subject,
            "purchaseOrderNumber": o.purchase_order_number,
            "status": o.status,
            "purchaseDate": str(o.purchase_date),
            "expectedDeliveryDate": str(o.expected_delivery_date) if o.expected_delivery_date else None,
            "owner": o.owner.full_name if o.owner else "—",
            "ownerId": o.owner.id if o.owner else None,
            "vendor": o.vendor.vendor_name,
            "vendorId": o.vendor.id,
            "billingAddress": _format_address(o.billing_address),
            "shippingAddress": _format_address(o.shipping_address),
            "termsAndConditions": o.terms_and_conditions,
            "description": o.description,
            "items": [
                {
                    "id": item.id,
                    "productId": item.product.id,
                    "productName": item.product.name,
                    "quantity": item.quantity,
                    "listPrice": float(item.list_price),
                    "discount": float(item.discount),
                    "tax": float(item.tax),
                    "lineTotal": float(item.line_total),
                    "description": item.description,
                }
                for item in o.items.all()
            ],
            "createdAt": o.created_at.isoformat(),
            "updatedAt": o.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_purchase_order(request, id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("owner", "vendor", "billing_address", "shipping_address").prefetch_related("items__product"),
        id=id, company=request.company
    )

    data = {
        "id": order.id,
        "subject": order.subject,
        "purchaseOrderNumber": order.purchase_order_number,
        "status": order.status,
        "purchaseDate": str(order.purchase_date),
        "expectedDeliveryDate": str(order.expected_delivery_date) if order.expected_delivery_date else None,
        "owner": order.owner.full_name if order.owner else "—",
        "ownerId": order.owner.id if order.owner else None,
        "vendor": order.vendor.vendor_name,
        "vendorId": order.vendor.id,
        "billingAddress": _format_address(order.billing_address),
        "shippingAddress": _format_address(order.shipping_address),
        "termsAndConditions": order.terms_and_conditions,
        "description": order.description,
        "items": [
            {
                "id": item.id,
                "productId": item.product.id,
                "productName": item.product.name,
                "quantity": item.quantity,
                "listPrice": float(item.list_price),
                "discount": float(item.discount),
                "tax": float(item.tax),
                "lineTotal": float(item.line_total),
                "description": item.description,
            }
            for item in order.items.all()
        ],
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_purchase_order(request, id):
    try:
        order = PurchaseOrder.objects.get(id=id, company=request.company)
    except PurchaseOrder.DoesNotExist:
        return HttpResponse("Purchase order not found", status=404)

    previous_owner_id = order.owner_id

    try:
        order.subject = request.data.get("subject") or order.subject
        order.status = request.data.get("status", order.status)
        order.terms_and_conditions = request.data.get("terms_and_conditions", order.terms_and_conditions)
        order.description = request.data.get("description", order.description)

        purchase_date = request.data.get("purchase_date")
        if purchase_date:
            order.purchase_date = purchase_date

        expected_delivery_date = request.data.get("expected_delivery_date")
        if expected_delivery_date:
            order.expected_delivery_date = expected_delivery_date

        owner_id = request.data.get("owner_id")
        if owner_id:
            order.owner_id = owner_id

        vendor_id = request.data.get("vendor_id")
        if vendor_id:
            order.vendor_id = vendor_id

        billing_data = request.data.get("billing_add")
        order.billing_address = _update_address(order.billing_address, billing_data)

        shipping_data = request.data.get("shipping_add")
        order.shipping_address = _update_address(order.shipping_address, shipping_data)

        order.save()

        items_data = request.data.get("items")
        if items_data is not None:
            order.items.all().delete()
            for item in items_data:
                PurchaseOrderItem.objects.create(
                    purchase_order=order,
                    product_id=item.get("product_id"),
                    quantity=int(item.get("quantity", 1)),
                    list_price=float(item.get("list_price", 0)),
                    discount=float(item.get("discount", 0)),
                    tax=float(item.get("tax", 0)),
                    description=item.get("description", ""),
                )

        if order.owner and order.owner_id != previous_owner_id and order.owner.user:
            try:
                notify_user(
                    company=request.company,
                    user=order.owner.user,
                    notification_type="purchase_order",
                    title="Purchase Order Assigned to You",
                    message=(
                        f"Hello {order.owner.full_name},\n\n"
                        f"A purchase order has been reassigned to you.\n\n"
                        f"Purchase Order: {order.purchase_order_number} - {order.subject}\n"
                        f"Vendor: {order.vendor.vendor_name}\n"
                        f"Status: {order.status}\n\n"
                        f"Please log in to the CRM to view the purchase order details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned purchase order %s", order.id)

        return HttpResponse("Purchase order updated successfully", status=200)

    except Exception as e:
        print("UPDATE PURCHASE ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_purchase_order(request, id):
    try:
        order = PurchaseOrder.objects.get(id=id, company=request.company)
        order.delete()
        return JsonResponse({"message": "Purchase order deleted successfully"})
    except PurchaseOrder.DoesNotExist:
        return HttpResponse("Purchase order not found", status=404)
    


# ............... case ...............
@api_view(['POST'])
def add_case(request):
    subject = request.data.get("subject")
    description = request.data.get("description")

    if not subject or not description:
        return HttpResponse("Subject and description are required", status=400)

    try:
        case = Case.objects.create(
            company=request.company,
            subject=subject,
            description=description,
            customer_id=request.data.get("customer_id") or None,
            account_id=request.data.get("account_id") or None,
            product_id=request.data.get("product_id") or None,
            assigned_to_id=request.data.get("assigned_to") or None,
            priority=request.data.get("priority", "medium"),
            status=request.data.get("status", "open"),
            source=request.data.get("source", "manual"),
            resolution=request.data.get("resolution", ""),
            created_by=request.staff,  # auto-fill logged in user
        )

        if case.assigned_to and case.assigned_to.user:
            try:
                notify_user(
                    company=request.company,
                    user=case.assigned_to.user,
                    notification_type="case_assigned",
                    title="New Case Assigned",
                    message=(
                        f"Hello {case.assigned_to.full_name},\n\n"
                        f"A new case has been assigned to you.\n\n"
                        f"Case: {case.case_number} - {case.subject}\n"
                        f"Priority: {case.priority}\n"
                        f"Status: {case.status}\n\n"
                        f"Please log in to the CRM to view the case details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for case %s", case.id)

        return JsonResponse({
            "message": "Case created successfully",
            "case_number": case.case_number,
            "id": case.id,
        }, status=201)

    except Exception as e:
        print("ADD CASE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_cases(request):
    cases = Case.objects.filter(company=request.company).select_related(
        "customer", "account", "product", "assigned_to", "created_by"
    ).order_by("-updated_at")

    data = []
    for c in cases:
        data.append({
            "c_name": c.company.name,
            "id": c.id,
            "caseNumber": c.case_number,
            "subject": c.subject,
            "description": c.description,
            "status": c.status,
            "priority": c.priority,
            "source": c.source,
            "resolution": c.resolution,
            "customer": c.customer.company_name if c.customer else "—",
            "customerId": c.customer.id if c.customer else None,
            "account": c.account.account_name if c.account else "—",
            "accountId": c.account.id if c.account else None,
            "product": c.product.name if c.product else "—",
            "productId": c.product.id if c.product else None,
            "assignedTo": c.assigned_to.full_name if c.assigned_to else "—",
            "assignedToId": c.assigned_to.id if c.assigned_to else None,
            "createdBy": c.created_by.full_name if c.created_by else "—",
            "closedAt": c.closed_at.isoformat() if c.closed_at else None,
            "createdAt": c.created_at.isoformat(),
            "updatedAt": c.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_case(request, id):
    case = get_object_or_404(
        Case.objects.select_related("customer", "account", "product", "assigned_to", "created_by"),
        id=id, company=request.company
    )

    return JsonResponse({
        "id": case.id,
        "caseNumber": case.case_number,
        "subject": case.subject,
        "description": case.description,
        "status": case.status,
        "priority": case.priority,
        "source": case.source,
        "resolution": case.resolution,
        "customer": case.customer.company_name if case.customer else "—",
        "customerId": case.customer.id if case.customer else None,
        "account": case.account.account_name if case.account else "—",
        "accountId": case.account.id if case.account else None,
        "product": case.product.name if case.product else "—",
        "productId": case.product.id if case.product else None,
        "assignedTo": case.assigned_to.full_name if case.assigned_to else "—",
        "assignedToId": case.assigned_to.id if case.assigned_to else None,
        "createdBy": case.created_by.full_name if case.created_by else "—",
        "closedAt": case.closed_at.isoformat() if case.closed_at else None,
        "createdAt": case.created_at.isoformat(),
        "updatedAt": case.updated_at.isoformat(),
    })


@api_view(['PUT'])
def update_case(request, id):
    try:
        case = Case.objects.get(id=id, company=request.company)
    except Case.DoesNotExist:
        return HttpResponse("Case not found", status=404)

    previous_staff_id = case.assigned_to_id

    try:
        case.subject = request.data.get("subject") or case.subject
        case.description = request.data.get("description") or case.description
        case.priority = request.data.get("priority") or case.priority
        case.status = request.data.get("status") or case.status
        case.source = request.data.get("source") or case.source
        case.resolution = request.data.get("resolution", case.resolution)

        customer_id = request.data.get("customer_id")
        if customer_id:
            case.customer_id = customer_id

        account_id = request.data.get("account_id")
        if account_id:
            case.account_id = account_id

        product_id = request.data.get("product_id")
        if product_id:
            case.product_id = product_id

        assigned_to_id = request.data.get("assigned_to")
        if assigned_to_id:
            case.assigned_to_id = assigned_to_id

        case.save()

        if case.assigned_to and case.assigned_to_id != previous_staff_id and case.assigned_to.user:
            try:
                notify_user(
                    company=request.company,
                    user=case.assigned_to.user,
                    notification_type="case_assigned",
                    title="Case Assigned to You",
                    message=(
                        f"Hello {case.assigned_to.full_name},\n\n"
                        f"A case has been reassigned to you.\n\n"
                        f"Case: {case.case_number} - {case.subject}\n"
                        f"Priority: {case.priority}\n"
                        f"Status: {case.status}\n\n"
                        f"Please log in to the CRM to view the case details."
                    ),
                )
            except Exception:
                logger.exception("Failed to notify staff for reassigned case %s", case.id)

        return HttpResponse("Case updated successfully", status=200)

    except Exception as e:
        print("UPDATE CASE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_case(request, id):
    try:
        case = Case.objects.get(id=id, company=request.company)
        case.delete()
        return JsonResponse({"message": "Case deleted successfully"})
    except Case.DoesNotExist:
        return HttpResponse("Case not found", status=404)
    


@api_view(['POST'])
def add_case_solution(request):
    company_id = request.data.get("company_id")
    title = request.data.get("title")
    category = request.data.get("category")
    content = request.data.get("content")
    status = request.data.get("status", "published")
    created_by_id = request.data.get("created_by_id")

    if not company_id or not title or not category or not content:
        return HttpResponse("company_id, title, category and content are required", status=400)

    company = get_object_or_404(Company, id=company_id)

    created_by = None
    if created_by_id:
        created_by = get_object_or_404(Staff, id=created_by_id)

    try:
        CaseSolution.objects.create(
            company=company,
            title=title,
            category=category,
            content=content,
            status=status,
            created_by=created_by,
        )
        return HttpResponse("Case solution created successfully", status=201)

    except Exception as e:
        print("ADD CASE SOLUTION ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_case_solutions(request):
    case_solutions = CaseSolution.objects.select_related("company", "created_by").all()

    company_id = request.query_params.get("company_id")
    if company_id:
        case_solutions = case_solutions.filter(company_id=company_id)

    category = request.query_params.get("category")
    if category:
        case_solutions = case_solutions.filter(category=category)

    status_param = request.query_params.get("status")
    if status_param:
        case_solutions = case_solutions.filter(status=status_param)

    data = []
    for cs in case_solutions:
        data.append({
            "id": cs.id,
            "companyId": cs.company.id,
            "companyName": cs.company.name if hasattr(cs.company, "name") else str(cs.company),
            "title": cs.title,
            "category": cs.category,
            "content": cs.content,
            "status": cs.status,
            "createdById": cs.created_by.id if cs.created_by else None,
            "createdByName": str(cs.created_by) if cs.created_by else "—",
            "createdAt": cs.created_at.isoformat(),
            "updatedAt": cs.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_case_solution(request, id):
    cs = get_object_or_404(CaseSolution.objects.select_related("company", "created_by"), id=id)

    data = {
        "id": cs.id,
        "companyId": cs.company.id,
        "companyName": cs.company.name if hasattr(cs.company, "name") else str(cs.company),
        "title": cs.title,
        "category": cs.category,
        "content": cs.content,
        "status": cs.status,
        "createdById": cs.created_by.id if cs.created_by else None,
        "createdByName": str(cs.created_by) if cs.created_by else "—",
        "createdAt": cs.created_at.isoformat(),
        "updatedAt": cs.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_case_solution(request, id):
    try:
        cs = CaseSolution.objects.get(id=id)
    except CaseSolution.DoesNotExist:
        return HttpResponse("Case solution not found", status=404)

    try:
        company_id = request.data.get("company_id")
        if company_id:
            cs.company = get_object_or_404(Company, id=company_id)

        cs.title = request.data.get("title") or cs.title
        cs.category = request.data.get("category") or cs.category
        cs.content = request.data.get("content") or cs.content
        cs.status = request.data.get("status", cs.status)

        created_by_id = request.data.get("created_by_id")
        if created_by_id:
            cs.created_by = get_object_or_404(Staff, id=created_by_id)
        elif created_by_id == "":
            cs.created_by = None

        cs.save()
        return HttpResponse("Case solution updated successfully", status=200)

    except Exception as e:
        print("UPDATE CASE SOLUTION ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_case_solution(request, id):
    try:
        cs = CaseSolution.objects.get(id=id)
        cs.delete()
        return JsonResponse({"message": "Case solution deleted successfully"})
    except CaseSolution.DoesNotExist:
        return HttpResponse("Case solution not found", status=404)
    


# ............... services ..................
@api_view(['POST'])
def add_service(request):
    service_name = request.data.get("service_name")
    service_code = request.data.get("service_code")
    unit_price = request.data.get("unit_price")

    if not service_name or not service_code or not unit_price:
        return HttpResponse("Service name, service code and unit price are required", status=400)

    if Service.objects.filter(service_code=service_code, company=request.company).exists():
        return HttpResponse("Service code already exists", status=400)

    try:
        Service.objects.create(
            company=request.company,
            service_name=service_name,
            service_code=service_code,
            category=request.data.get("category", ""),
            description=request.data.get("description", ""),
            unit_price=unit_price,
            tax_percentage=request.data.get("tax_percentage", 0),
            billing_type=request.data.get("billing_type", "fixed"),
            duration=request.data.get("duration", ""),
            status=request.data.get("status", "active"),
        )
        return HttpResponse("Service created successfully", status=201)

    except Exception as e:
        print("ADD SERVICE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_services(request):
    services = Service.objects.filter(company=request.company)

    data = []
    for s in services:
        data.append({
            "c.name": s.company.name,
            "id": s.id,
            "serviceName": s.service_name,
            "serviceCode": s.service_code,
            "category": s.category,
            "description": s.description,
            "unitPrice": float(s.unit_price),
            "taxPercentage": float(s.tax_percentage),
            "billingType": s.billing_type,
            "duration": s.duration,
            "status": s.status,
            "createdAt": s.created_at.isoformat(),
            "updatedAt": s.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_service(request, id):
    service = get_object_or_404(Service, id=id, company=request.company)

    return JsonResponse({
        "c.name": service.company.name,
        "id": service.id,
        "serviceName": service.service_name,
        "serviceCode": service.service_code,
        "category": service.category,
        "description": service.description,
        "unitPrice": float(service.unit_price),
        "taxPercentage": float(service.tax_percentage),
        "billingType": service.billing_type,
        "duration": service.duration,
        "status": service.status,
        "createdAt": service.created_at.isoformat(),
        "updatedAt": service.updated_at.isoformat(),
    })


@api_view(['PUT'])
def update_service(request, id):
    try:
        service = Service.objects.get(id=id, company=request.company)
    except Service.DoesNotExist:
        return HttpResponse("Service not found", status=404)

    try:
        service.service_name = request.data.get("service_name") or service.service_name
        service.category = request.data.get("category", service.category)
        service.description = request.data.get("description", service.description)
        service.unit_price = request.data.get("unit_price") or service.unit_price
        service.tax_percentage = request.data.get("tax_percentage", service.tax_percentage)
        service.billing_type = request.data.get("billing_type", service.billing_type)
        service.duration = request.data.get("duration", service.duration)
        service.status = request.data.get("status", service.status)

        new_code = request.data.get("service_code")
        if new_code and new_code != service.service_code:
            if Service.objects.filter(service_code=new_code, company=request.company).exists():
                return HttpResponse("Service code already exists", status=400)
            service.service_code = new_code

        service.save()
        return HttpResponse("Service updated successfully", status=200)

    except Exception as e:
        print("UPDATE SERVICE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_service(request, id):
    try:
        service = Service.objects.get(id=id, company=request.company)
        service.delete()
        return JsonResponse({"message": "Service deleted successfully"})
    except Service.DoesNotExist:
        return HttpResponse("Service not found", status=404)

# ............. profile ..............
def _serialize_profile(staff):
    addr = staff.address
    return {
        "id": staff.id,
        "fullName": staff.full_name,
        "lastName": staff.last_name,
        "email": staff.email,
        "role": staff.get_role_display() if staff.role else "",
        "roleValue": staff.role,
        "department": staff.department,
        "profileType": staff.profile_type,
        "mobile": staff.mobile,
        "website": staff.website,
        "fax": staff.fax,
        "alias": staff.alias,
        "dateOfBirth": staff.date_of_birth.isoformat() if staff.date_of_birth else "",
        "street": addr.street_address if addr else "",
        "city": addr.city if addr else "",
        "state": addr.state if addr else "",
        "zipCode": addr.zip_code if addr else "",
        "country": addr.country if addr else "",
        "addedBy": staff.added_by.full_name if staff.added_by else "",
    }


@api_view(["GET"])
def get_profile(request):
    return Response(_serialize_profile(request.staff))


@api_view(["PATCH"])
def update_profile(request):
    staff = request.staff
    data = request.data

    editable_fields = [
        ("full_name", "fullName"),
        ("last_name", "lastName"),
        ("mobile", "mobile"),
        ("website", "website"),
        ("fax", "fax"),
        ("alias", "alias"),
        ("profile_type", "profileType"),
    ]

    for model_field, payload_key in editable_fields:
        if payload_key in data:
            setattr(staff, model_field, data.get(payload_key) or "")

    if "dateOfBirth" in data:
        raw_dob = data.get("dateOfBirth")
        staff.date_of_birth = parse_date(raw_dob) if raw_dob else None

    address_fields = {
        "street_address": data.get("street"),
        "city": data.get("city"),
        "state": data.get("state"),
        "zip_code": data.get("zipCode"),
        "country": data.get("country"),
    }
    has_address_data = any(v for v in address_fields.values())

    if has_address_data:
        if staff.address is None:
            staff.address = Address.objects.create(**{k: v or "" for k, v in address_fields.items()})
        else:
            for field, value in address_fields.items():
                if value is not None:
                    setattr(staff.address, field, value)
            staff.address.save()

    staff.save()
    return Response(_serialize_profile(staff))



# ............. notification ...............
FIELD_MAP = {
    "dailyDigest": "email_daily_digest",
    "newLeadAlerts": "email_new_lead_alerts",
    "systemUpdates": "email_system_updates",
    "taskAssignments": "email_task_assignments",
    "emailMeetingReminders": "email_meeting_reminders",
    "callAssignments": "email_call_assignments",
    "dealAssignments": "email_deal_assignments",
    "caseAssignments": "email_case_assignments",
    "salesOrderUpdates": "email_sales_order_updates",
    "purchaseOrderUpdates": "email_purchase_order_updates",
    "invoiceUpdates": "email_invoice_updates",
    "highPriorityTasks": "push_high_priority_tasks",
    "meetingReminders": "push_meeting_reminders",
    "activityBellDot": "inapp_activity_bell",
    "toastAlerts": "inapp_toast_alerts",
    "notificationSound": "desktop_notification_sound",
    "floatingPreview": "desktop_floating_preview",
}

def to_camel(pref):
    return {camel: getattr(pref, field) for camel, field in FIELD_MAP.items()}


@api_view(['GET', 'PUT'])
def notification_preferences(request):
    pref, _ = NotificationPreference.objects.get_or_create(
        company=request.company, user=request.user
    )

    if request.method == 'GET':
        return JsonResponse(to_camel(pref))

    if request.method == 'PUT':
        data = request.data
        unknown_keys = [k for k in data.keys() if k not in FIELD_MAP]
        if unknown_keys:
            return JsonResponse(
                {"error": f"Unknown field(s): {', '.join(unknown_keys)}"},
                status=400
            )

        for camel, field in FIELD_MAP.items():
            if camel in data:
                setattr(pref, field, bool(data[camel]))
        pref.save()
        return JsonResponse(to_camel(pref))


@api_view(["GET"])
def get_notifications(request):
    notifications = Notification.objects.filter(
        company=request.company,
        user=request.user
    )

    data = [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in notifications
    ]

    return Response(data)

@api_view(["GET"])
def get_unread_count(request):
    count = Notification.objects.filter(
        company=request.company,
        user=request.user,
        is_read=False
    ).count()

    return Response({"count": count})

@api_view(["PUT"])
def mark_notification_read(request, id):
    notification = get_object_or_404(
        Notification,
        id=id,
        company=request.company,
        user=request.user,
    )

    notification.is_read = True
    notification.save()

    return Response({"message": "Success"})

@api_view(["PUT"])
def mark_all_notifications_read(request):
    Notification.objects.filter(
        company=request.company,
        user=request.user,
        is_read=False,
    ).update(is_read=True)

    return Response({"message": "Success"})



# ............... change pass ...............

@api_view(['POST'])
def change_password(request):
    user = request.user

    current_password = request.data.get("current_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not current_password or not new_password or not confirm_password:
        return Response({"message": "All fields are required"}, status=400)

    if new_password != confirm_password:
        return Response({"message": "New password and confirm password do not match"}, status=400)

    if not user.check_password(current_password):
        return Response({"message": "Current password is incorrect"}, status=400)

    if len(new_password) < 8:
        return Response({"message": "New password must be at least 8 characters long"}, status=400)

    if current_password == new_password:
        return Response({"message": "New password must be different from the current password"}, status=400)

    try:
        user.set_password(new_password)
        user.save()
        return Response({"message": "Password updated successfully"}, status=200)
    except Exception as e:
        return Response({"message": str(e)}, status=500)
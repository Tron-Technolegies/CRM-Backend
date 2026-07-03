from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from rest_framework.decorators import api_view
from django.db.models import Sum
from django.db.models.functions import TruncWeek
from django.db.models import Count
from django.db import transaction

from AdminApp.models import Accounts, Address, Call, Customer, Deal, Lead, Meeting, PicklistOption, PriceBook, PriceBookItem, Product, QuoteProduct, Quotes, SalesOrder, SalesOrderItem, Staff, Task, Vendor

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt



# .............. authentication..............
@api_view(['POST'])
def user_signup(request):
    name = request.data.get("name")
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password or not name:
        return Response({"message": "Name, email and password are required"}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"message": "Email already exists"}, status=400)

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
    )

    # Create Staff with no role/department — super admin assigns later
    Staff.objects.create(
        user=user,
        full_name=name,
        email=email,
        role="",
        department="",
        is_invited=False,
    )

    return Response({"message": "Account created successfully"})



@api_view(['POST'])
def user_login(request):
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response({"message": "Email and password are required"}, status=400)

    try:
        user_obj = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"message": "Invalid credentials"}, status=401)

    user = authenticate(username=user_obj.username, password=password)

    if user is None:
        return Response({"message": "Invalid credentials"}, status=401)

    # Get linked staff via OneToOne relation
    try:
        staff = user.staff
        staff_data = {
            "id": staff.id,
            "fullName": staff.full_name,
            "role": staff.role,
            "department": staff.department,
        }
    except Staff.DoesNotExist:
        staff_data = None

    refresh = RefreshToken.for_user(user)

    return JsonResponse({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.first_name,
            "staff": staff_data,
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


# ..............lead.......................
@api_view(['POST'])
def add_lead(request):
    full_name = request.data.get("full_name")
    phone_number = request.data.get("phone_number")
    email = request.data.get("email")
    company_name = request.data.get("company_name")
    lead_source = request.data.get("lead_source")
    assigned_to = request.data.get("assigned_to")
    priority = request.data.get("priority")
    expected_closing_date = request.data.get("expected_closing_date")
    lead_description = request.data.get("lead_description")

    if not full_name or not phone_number:
        return HttpResponse(
            "Full name and phone number are mandatory fields",
            status=400
        )

    try:
        Lead.objects.create(
            full_name=full_name,
            phone_number=phone_number,
            email=email,
            company_name=company_name,
            lead_source=lead_source,
            assigned_to_id=assigned_to,
            assigned_to=None,
            priority=priority,
            expected_closing_date=expected_closing_date,
            lead_description=lead_description,
        )

        return HttpResponse("Lead created successfully", status=201)

    except Exception as e:
        print("ADD LEAD ERROR:", str(e))
        return HttpResponse(str(e), status=500)



@api_view(['GET'])
def view_leads(request):
    leads = Lead.objects.all().order_by('-updated_at')
    list = []

    for i in leads:
        list.append(
            {
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
    lead = get_object_or_404(Lead, id=id)
    
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
        lead = Lead.objects.get(id=id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

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
        return HttpResponse("Lead updated successfully", status=200)
    except Exception as e:
        print("SAVE ERROR:", str(e))
        return HttpResponse(str(e), status=500)



@api_view(['DELETE'])
def delete_lead(request, id):
    data = Lead.objects.get(id=id)
    data.delete()
    return JsonResponse({"message": "successfully deleted"})


# ...............deal....................
# ............ add lead id in add deal ..............
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
    lead_id = request.data.get("lead_id")          # ← optional lead link

    if not deal_name or not company_name:
        return HttpResponse(
            "Deal name and company name are mandatory fields",
            status=400
        )

    # fetch lead if lead_id is provided
    lead = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return HttpResponse("Lead not found", status=404)

    try:
        Deal.objects.create(
            deal_name=deal_name,
            company_name=company_name,
            deal_amount=deal_amount,
            stage=stage,
            assigned_to_id=assigned_to,
            expected_close_date=expected_close_date,
            deal_source=deal_source,
            priority=priority,
            deal_description=deal_description,
            lead=lead,                              # 🔗 link lead if provided
        )

        # mark lead as converted if linked
        if lead:
            lead.status = "converted"
            lead.converted_at = timezone.now()
            lead.save()

        return HttpResponse("Deal created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['GET'])
def view_deals(request):
    deals = Deal.objects.all().order_by('-updated_at')
    list = []

    for i in deals:
        list.append({
            "id": i.id,
            "name": i.deal_name,
            "company_name": i.company_name,
            "stage": i.stage,
            "value": float(i.deal_amount) if i.deal_amount else 0,
            "expectedCloseDate": str(i.expected_close_date) if i.expected_close_date else "—",
            "assignedTo": i.assigned_to.full_name if i.assigned_to else "—",
            "assignedToId": i.assigned_to.id if i.assigned_to else None,
            "source": i.deal_source,
            "priority": i.priority,
            "description": i.deal_description,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
        })
    return JsonResponse(list, safe=False)



@api_view(['GET'])
def view_single_deals(request, id):
    deal = get_object_or_404(Deal, id=id)

    data = {
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
            }
    return JsonResponse(data, safe=False)



@api_view(['PUT'])
def update_deal(request, id):
    try:
        deal = Deal.objects.get(id=id)
    except Deal.DoesNotExist:
        return HttpResponse("Dead not found", status=404)

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

    try:
        deal.save()
        return HttpResponse("Deal updated successfully", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['DELETE'])
def delete_deal(request, id):
    data = Deal.objects.get(id=id)
    data.delete()
    return JsonResponse({"message": "successfully deleted"})



# ...................customer...................
@api_view(['POST'])
def add_customer(request):
    company_name = request.data.get("company_name")
    contact_name = request.data.get("contact_name")
    phone_number = request.data.get("phone_number")
    email = request.data.get("email")
    industry = request.data.get("industry")
    status = request.data.get("status")
    lifetime_value = request.data.get("lifetime_value")
    deal_id = request.data.get("deal_id")

    if not company_name or not contact_name or not phone_number:
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

    try:
        customer = Customer.objects.create(
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

        return HttpResponse("Customer created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)



@api_view(['GET'])
def view_customers(request):
    customers = Customer.objects.all().order_by('-updated_at')
    data = []

    for i in customers:
        data.append({
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
    customer = get_object_or_404(Customer, id=id)

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
        customer = Customer.objects.get(id=id)
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
    customer = Customer.objects.get(id=id)
    customer.delete()
    return JsonResponse({"message": "Customer deleted successfully"})



# .................task..................
@api_view(['POST'])
def add_task(request):
    title = request.data.get("title")
    description = request.data.get("description")
    assigned_to = request.data.get("assigned_to")
    related_to = request.data.get("related_to")
    priority = request.data.get("priority")
    status = request.data.get("status")
    due_date = request.data.get("due_date")

    if not title or not due_date:
        return HttpResponse("Title and due_date are mandatory fields", status=400)

    # normalize status
    status_map = {
        "pending": "pending",
        "in progress": "in_progress",
        "in_progress": "in_progress",
        "completed": "completed",
    }
    status = status_map.get(status.lower() if status else "pending", "pending")

    try:
        Task.objects.create(
            title=title,
            description=description,
            assigned_to=None,
            related_to=related_to,
            priority=priority,
            status=status,
            due_date=due_date,
        )
        return HttpResponse("Task created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['GET'])
def view_tasks(request):
    tasks = Task.objects.all().order_by('-updated_at')
    data = []

    for i in tasks:
        data.append({
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "assignedTo": i.assigned_to.full_name if i.assigned_to else "—",
            "assignedToId": i.assigned_to.id if i.assigned_to else None,
            "relatedTo": i.related_to,
            "priority": i.priority,
            "status": i.status,
            "dueDate": str(i.due_date) if i.due_date else None,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
        })

    return JsonResponse(data, safe=False)



@api_view(['GET'])
def view_single_task(request, id):
    task = get_object_or_404(Task, id=id)

    data = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "assignedTo": task.assigned_to.full_name if task.assigned_to else "—",
                "assignedToId": task.assigned_to.id if task.assigned_to else None,
                "relatedTo": task.related_to,
                "priority": task.priority,
                "status": task.status,
                "dueDate": str(task.due_date) if task.due_date else None,
                "createdAt": task.created_at.isoformat() if task.created_at else None,
            }

    return JsonResponse(data, safe=False)



@api_view(['PUT'])
def update_task(request, id):
    try:
        task = Task.objects.get(id=id)

    except Task.DoesNotExist:
        return HttpResponse("Task not found", status=404)

    task.title = request.data.get("title") or task.title
    task.description = request.data.get("description") or task.description
    task.related_to = request.data.get("related_to") or task.related_to
    task.priority = request.data.get("priority") or task.priority
    task.status = request.data.get("status") or task.status
    task.due_date = request.data.get("due_date") or task.due_date

    assigned_to_id = request.data.get("assigned_to")
    if assigned_to_id:
        task.assigned_to = get_object_or_404(Staff, id=assigned_to_id)
    else:
        task.assigned_to = None

    try:
        task.save()
        return HttpResponse("Task updated successfully", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['DELETE'])
def delete_task(request, id):
        task = Task.objects.get(id=id)
        task.delete()
        return JsonResponse({"message": "Task deleted successfully"})



# ............staff(user)...............
@api_view(['POST'])
def add_staff(request):
    full_name = request.data.get("full_name")
    email = request.data.get("email")
    role = request.data.get("role")
    department = request.data.get("department")

    if not full_name or not email or not role:
        return HttpResponse(
            "Full name, email and role are mandatory fields",
            status=400
        )

    try:
        Staff.objects.create(
            full_name=full_name,
            email=email,
            role=role,
            department=department,
            is_invited=True,
        )

        return HttpResponse("Staff created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['GET'])
def view_staff(request):
    staffs = Staff.objects.all().order_by('-invited_at')
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
        })

    return JsonResponse(data, safe=False)



@api_view(['GET'])
def view_single_staff(request, id):
    staff = get_object_or_404(Staff, id=id)

    data = {
                "id": staff.id,
                "fullName": staff.full_name,
                "email": staff.email,
                "role": staff.role,
                "department": staff.department,
                "status": "Invited" if staff.is_invited else "Active",
                "invitedAt": staff.invited_at.isoformat() if staff.invited_at else None,
            }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_staff(request, id):
    try:
        staff = Staff.objects.get(id=id)
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
    staff = Staff.objects.get(id=id)
    staff.delete()
    return JsonResponse({"message": "Staff deleted successfully"})



# ............report.............
from datetime import datetime

@api_view(['GET'])
def report_view(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    leads_qs = Lead.objects.all()
    deals_qs = Deal.objects.all()
    customers_qs = Customer.objects.all()
    tasks_qs = Task.objects.all()

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
def convert_lead_to_customer(request, lead_id):

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    if lead.status == "converted":
        return HttpResponse("Lead already converted to a customer", status=400)

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
# ............ unconverted lead show in dropdown ........
@api_view(['GET'])
def get_unconverted_leads(request):
    leads = Lead.objects.exclude(status="converted")
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
    from django.db.models import Count
    sources = Lead.objects.values('lead_source').annotate(count=Count('id'))
    total = Lead.objects.count()
    
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
            "name": s['lead_source'],
            "value": round((s['count'] / total) * 100) if total > 0 else 0,
            "color": colors.get(s['lead_source'], "#64748B"),
        }
        for s in sources
    ]

    return JsonResponse({"data": data, "total": total})



# .......... Add, Edit, View, Delete the choices ...........

@api_view(['GET'])
def view_picklists(request):
    field = request.GET.get("field")
    qs = PicklistOption.objects.filter(is_active=True)
    if field:
        qs = qs.filter(field=field)
    data = [{"id": o.id, "field": o.field, "value": o.value, "label": o.label, "order": o.order} for o in qs]
    return JsonResponse(data, safe=False)


@api_view(['POST'])
def add_picklist_option(request):
    field = request.data.get("field")
    value = request.data.get("value")
    label = request.data.get("label")

    if not field or not value or not label:
        return HttpResponse("field, value and label are required", status=400)

    if PicklistOption.objects.filter(field=field, value=value).exists():
        return HttpResponse("This option already exists", status=400)

    max_order = PicklistOption.objects.filter(field=field).count()
    PicklistOption.objects.create(field=field, value=value, label=label, order=max_order)
    return HttpResponse("Option added successfully", status=201)


@api_view(['PUT'])
def update_picklist_option(request, id):
    try:
        option = PicklistOption.objects.get(id=id)
    except PicklistOption.DoesNotExist:
        return HttpResponse("Option not found", status=404)

    option.label = request.data.get("label") or option.label
    option.is_active = request.data.get("is_active", option.is_active)
    option.save()
    return HttpResponse("Option updated successfully", status=200)


@api_view(['DELETE'])
def delete_picklist_option(request, id):
    try:
        option = PicklistOption.objects.get(id=id)
        option.delete()
        return JsonResponse({"message": "Option deleted successfully"})
    except PicklistOption.DoesNotExist:
        return HttpResponse("Option not found", status=404)
    


# .............. account ................
@csrf_exempt
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
    

@csrf_exempt
@api_view(['GET'])
def view_accounts(request):
    accounts = Accounts.objects.select_related(
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



@csrf_exempt
@api_view(['PUT'])
def update_account(request, id):
    try:
        account = Accounts.objects.get(id=id)
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
    account = Accounts.objects.get(id=id)
    account.delete()
    return JsonResponse({"message": "Account deleted successfully"})



# ................. quotes ..................
# Helper to serialize products
def _serialize_products(quote):
    products = []

    for item in quote.items.all():
        products.append({
            "product": {
                "id": item.product.id,
                "name": item.product.name,
            },
            "quantity": item.quantity,
            "listPrice": float(item.list_price),
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
    billing_data = request.data.get("billing_add")
    shipping_data = request.data.get("shipping_add")
    
    # 1. Grab the products array from payload
    products_data = request.data.get("products", []) 

    if not subject:
        return HttpResponse("Subject is required", status=400)

    try:
        deal = None
        account = None

        if deal_id:
            try:
                deal = Deal.objects.get(id=deal_id)
            except Deal.DoesNotExist:
                return HttpResponse("Deal not found", status=404)

        if account_id:
            try:
                account = Accounts.objects.select_related("billing_address", "shipping_address").get(id=account_id)
            except Accounts.DoesNotExist:
                return HttpResponse("Account not found", status=404)
        elif deal and deal.account_id: # Updated to your customer target field safely
            account = deal.account 

        # Wrap database operations in an atomic block
        with transaction.atomic():
            billing_address = None
            if billing_data:
                billing_address = Address.objects.create(**billing_data)
            elif account and account.billing_address:
                src = account.billing_address
                billing_address = Address.objects.create(
                    country=src.country, address=src.address,street_address=src.street_address, city=src.city, state=src.state, zip_code=src.zip_code
                )

            shipping_address = None
            if shipping_data:
                shipping_address = Address.objects.create(**shipping_data)
            elif account and account.shipping_address:
                src = account.shipping_address
                shipping_address = Address.objects.create(
                    country=src.country, address=src.address,street_address=src.street_address, city=src.city, state=src.state, zip_code=src.zip_code
                )

            # 2. Save the primary Quote header record
            quote = Quotes.objects.create(
                subject=subject,
                quote_stage=quote_stage,
                valid_until=valid_until or None,
                assigned_to_id=assigned_to_id or None,
                deal=deal,
                contact_name=contact_name,
                account=account,
                billing_address=billing_address,
                shipping_address=shipping_address,
            )

            # 3. Create individual QuoteProduct instances safely inside transaction block
            for item in products_data:
                product = get_object_or_404(Product, id=item.get("product"))

                quantity = int(item.get("quantity", 1))
                list_price = product.unit_price
                discount = float(item.get("discount", 0))
                tax = float(product.tax_percentage)

                amount = quantity * float(list_price)
                total = (amount - discount) + ((amount - discount) * tax / 100)

                QuoteProduct.objects.create(
                    quote=quote,
                    product=product,
                    description=product.description,
                    quantity=quantity,
                    list_price=list_price,
                    amount=amount,
                    discount=discount,
                    tax=tax,
                    total=total,
                )

        return HttpResponse("Quote and line items created successfully", status=201)

    except Exception as e:
        print("ADD QUOTE ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_quotes(request):
    # Added "items" prefetching to dramatically boost query execution speed
    quotes = Quotes.objects.prefetch_related("items").select_related(
        "assigned_to", "deal", "account", "billing_address", "shipping_address"
    ).all().order_by("-updated_at")

    data = []
    for i in quotes:
        data.append({
            "id": i.id,
            "subject": i.subject,
            "quoteStage": i.quote_stage,
            "validUntil": str(i.valid_until) if i.valid_until else None,
            "assignedTo": i.assigned_to.full_name if i.assigned_to else "—",
            "dealName": i.deal.deal_name if i.deal else "—",
            "accountName": i.account.account_name if i.account else None,
            "billingAddress": _serialize_address(i.billing_address),
            "shippingAddress": _serialize_address(i.shipping_address),
            "products": _serialize_products(i), # Appends the linked items list to the JSON payload
            "createdAt": i.created_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_quote(request, id):
    quote = get_object_or_404(
        Quotes.objects.prefetch_related("items").select_related(
            "assigned_to", "deal", "account", "billing_address", "shipping_address"
        ),
        id=id
    )

    data = {
        "id": quote.id,
        "subject": quote.subject,
        "quoteStage": quote.quote_stage,
        "validUntil": str(quote.valid_until) if quote.valid_until else None,
        "contactName": quote.contact_name,
        "products": _serialize_products(quote), # Exposes itemized items detail arrays out cleanly
        "billingAddress": _serialize_address(quote.billing_address),
        "shippingAddress": _serialize_address(quote.shipping_address),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_quote(request, id):
    try:
        quote = Quotes.objects.get(id=id)
    except Quotes.DoesNotExist:
        return HttpResponse("Quote not found", status=404)

    try:
        with transaction.atomic():
            quote.subject = request.data.get("subject") or quote.subject
            quote.quote_stage = request.data.get("quote_stage") or quote.quote_stage
            
            # Simple metadata overrides
            if "valid_until" in request.data: quote.valid_until = request.data.get("valid_until")
            if "assigned_to" in request.data: quote.assigned_to_id = request.data.get("assigned_to")

            quote.save()

            # Dynamic Item Synchronizer Block
            products_data = request.data.get("products")
            if products_data is not None:
                quote.items.all().delete()
                for item in products_data:
                    product = get_object_or_404(Product, id=item.get("product"))

                    quantity = int(item.get("quantity", 1))
                    list_price = product.unit_price
                    discount = float(item.get("discount", 0))
                    tax = float(product.tax_percentage)

                    amount = quantity * float(list_price)
                    total = (amount - discount) + ((amount - discount) * tax / 100)

                    QuoteProduct.objects.create(
                        quote=quote,
                        product=product,
                        description=item.get("description", product.description),
                        quantity=quantity,
                        list_price=list_price,
                        amount=amount,
                        discount=discount,
                        tax=tax,
                        total=total,
                    )

        return HttpResponse("Quote updated successfully", status=200)

    except Exception as e:
        return HttpResponse(str(e), status=500)
    

@api_view(['DELETE'])
def delete_quote(request, id):
    try:
        quote = Quotes.objects.select_related(
            "billing_address", "shipping_address"
        ).get(id=id)

        billing = quote.billing_address
        shipping = quote.shipping_address

        quote.delete()

        if billing and billing.id is not None:
            billing.delete()
        if shipping and shipping.id is not None:
            shipping.delete()

        return JsonResponse({"message": "Quote deleted successfully"})

    except Quotes.DoesNotExist:
        return HttpResponse("Quote not found", status=404)
    


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
    repeat = request.data.get("repeat", "none")

    if not title or not from_datetime or not to_datetime:
        return HttpResponse("Title, from_datetime and to_datetime are required", status=400)

    try:
        meeting = Meeting.objects.create(
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
            repeat=repeat,
        )

        if participant_ids:
            meeting.participants.set(participant_ids)

        return HttpResponse("Meeting created successfully", status=201)

    except Exception as e:
        print("ADD MEETING ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_meetings(request):
    meetings = Meeting.objects.select_related(
        "host", "related_lead", "related_customer"
    ).prefetch_related("participants").all().order_by("-created_at")

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
            "repeat": m.repeat,
            "createdAt": m.created_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_meeting(request, id):
    meeting = get_object_or_404(
        Meeting.objects.select_related("host", "related_lead", "related_customer").prefetch_related("participants"),
        id=id
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
        "repeat": meeting.repeat,
        "createdAt": meeting.created_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_meeting(request, id):
    try:
        meeting = Meeting.objects.get(id=id)
    except Meeting.DoesNotExist:
        return HttpResponse("Meeting not found", status=404)

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
            elif related_type == "customer":
                meeting.related_customer_id = request.data.get("related_customer") or None
                meeting.related_lead = None
            else:
                meeting.related_lead = None
                meeting.related_customer = None

        meeting.save()

        participant_ids = request.data.get("participants")
        if participant_ids is not None:
            meeting.participants.set(participant_ids)

        return HttpResponse("Meeting updated successfully", status=200)

    except Exception as e:
        print("UPDATE MEETING ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_meeting(request, id):
    try:
        meeting = Meeting.objects.get(id=id)
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

    if not subject or not call_type or not start_time or not duration:
        return HttpResponse("Subject, call_type, start_time and duration are required", status=400)

    try:
        call = Call.objects.create(
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
        )

        return HttpResponse("Call created successfully", status=201)

    except Exception as e:
        print("ADD CALL ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_calls(request):
    calls = Call.objects.select_related(
        "assigned_to", "lead", "contact", "deal"
    ).all().order_by("-start_time")

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
            "relatedType": "lead" if c.lead else "contact" if c.contact else "deal" if c.deal else "none",
            "relatedLead": {"id": c.lead.id, "name": c.lead.full_name} if c.lead else None,
            "relatedContact": {"id": c.contact.id, "name": c.contact.company_name} if c.contact else None,
            "relatedDeal": {"id": c.deal.id, "name": c.deal.deal_name} if c.deal else None,
            "createdAt": c.created_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_call(request, id):
    call = get_object_or_404(
        Call.objects.select_related("assigned_to", "lead", "contact", "deal"),
        id=id
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
        "relatedType": "lead" if call.lead else "contact" if call.contact else "deal" if call.deal else "none",
        "relatedLead": {"id": call.lead.id, "name": call.lead.full_name} if call.lead else None,
        "relatedContact": {"id": call.contact.id, "name": call.contact.company_name} if call.contact else None,
        "relatedDeal": {"id": call.deal.id, "name": call.deal.deal_name} if call.deal else None,
        "createdAt": call.created_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_call(request, id):
    try:
        call = Call.objects.get(id=id)
    except Call.DoesNotExist:
        return HttpResponse("Call not found", status=404)

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
            if related_type == "lead":
                call.lead_id = request.data.get("related_lead") or None
            elif related_type == "contact":
                call.contact_id = request.data.get("related_contact") or None
            elif related_type == "deal":
                call.deal_id = request.data.get("related_deal") or None

        call.save()
        return HttpResponse("Call updated successfully", status=200)

    except Exception as e:
        print("UPDATE CALL ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_call(request, id):
    try:
        call = Call.objects.get(id=id)
        call.delete()
        return JsonResponse({"message": "Call deleted successfully"})
    except Call.DoesNotExist:
        return HttpResponse("Call not found", status=404)
    


# .............. vendor ................
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
    address = request.data.get("address", "")
    city = request.data.get("city", "")
    state = request.data.get("state", "")
    country = request.data.get("country", "")
    postal_code = request.data.get("postal_code", "")
    status = request.data.get("status", "active")
    notes = request.data.get("notes", "")

    if not vendor_name or not vendor_code:
        return HttpResponse("Vendor name and vendor code are required", status=400)

    if Vendor.objects.filter(vendor_code=vendor_code).exists():
        return HttpResponse("Vendor code already exists", status=400)

    try:
        Vendor.objects.create(
            vendor_name=vendor_name,
            vendor_code=vendor_code,
            contact_person=contact_person,
            email=email,
            phone=phone,
            mobile=mobile,
            website=website,
            gst_number=gst_number,
            address=address,
            city=city,
            state=state,
            country=country,
            postal_code=postal_code,
            status=status,
            notes=notes,
        )
        return HttpResponse("Vendor created successfully", status=201)

    except Exception as e:
        print("ADD VENDOR ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_vendors(request):
    vendors = Vendor.objects.all().order_by("-updated_at")

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
            "address": v.address,
            "city": v.city,
            "state": v.state,
            "country": v.country,
            "postalCode": v.postal_code,
            "status": v.status,
            "notes": v.notes,
            "createdAt": v.created_at.isoformat(),
            "updatedAt": v.updated_at.isoformat(),
        })

    return JsonResponse(data, safe=False)


@api_view(['GET'])
def view_single_vendor(request, id):
    vendor = get_object_or_404(Vendor, id=id)

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
        "address": vendor.address,
        "city": vendor.city,
        "state": vendor.state,
        "country": vendor.country,
        "postalCode": vendor.postal_code,
        "status": vendor.status,
        "notes": vendor.notes,
        "createdAt": vendor.created_at.isoformat(),
        "updatedAt": vendor.updated_at.isoformat(),
    }

    return JsonResponse(data, safe=False)


@api_view(['PUT'])
def update_vendor(request, id):
    try:
        vendor = Vendor.objects.get(id=id)
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
        vendor.address = request.data.get("address", vendor.address)
        vendor.city = request.data.get("city", vendor.city)
        vendor.state = request.data.get("state", vendor.state)
        vendor.country = request.data.get("country", vendor.country)
        vendor.postal_code = request.data.get("postal_code", vendor.postal_code)
        vendor.status = request.data.get("status", vendor.status)
        vendor.notes = request.data.get("notes", vendor.notes)

        # vendor_code is unique — only update if provided and different
        new_code = request.data.get("vendor_code")
        if new_code and new_code != vendor.vendor_code:
            if Vendor.objects.filter(vendor_code=new_code).exists():
                return HttpResponse("Vendor code already exists", status=400)
            vendor.vendor_code = new_code

        vendor.save()
        return HttpResponse("Vendor updated successfully", status=200)

    except Exception as e:
        print("UPDATE VENDOR ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_vendor(request, id):
    try:
        vendor = Vendor.objects.get(id=id)
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
    products = Product.objects.select_related("vendor").all()

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
    product = get_object_or_404(Product.objects.select_related("vendor"), id=id)

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
        product = Product.objects.get(id=id)
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
        product = Product.objects.get(id=id)
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
        price_book = PriceBook.objects.get(id=id)
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
        price_book = PriceBook.objects.get(id=id)
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
        item = PriceBookItem.objects.get(id=id)
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
        item = PriceBookItem.objects.get(id=id)
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
    """Fetch quote data to prefill sales order form"""
    quote = get_object_or_404(
        Quotes.objects.select_related(
            "assigned_to", "deal", "account",
            "billing_address", "shipping_address"
        ),
        id=quote_id
    )

    # Get quote items if any (via sales orders linked to this quote)
    items = []

    return JsonResponse({
        "subject": quote.subject,
        "contactName": quote.contact_name,
        "accountName": quote.account.account_name if quote.account else "",
        "dealId": quote.deal.id if quote.deal else None,
        "dealName": quote.deal.deal_name if quote.deal else "",
        "billingAddress": _format_address(quote.billing_address),
        "shippingAddress": _format_address(quote.shipping_address),
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

        # Fetch the quote once if linked, and reuse it for address/deal/items
        if quote_id:
            try:
                quote = Quotes.objects.select_related(
                    "billing_address", "shipping_address"
                ).prefetch_related("items").get(id=quote_id)
            except Quotes.DoesNotExist:
                quote = None

        # --- Address auto-fill ---
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

        # --- Deal auto-fill ---
        if quote and not deal_id:
            deal_id = quote.deal_id  # adjust field name if it's e.g. quote.deal.id

        sales_order = SalesOrder.objects.create(
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

        # --- Items: use request items if given, else pull from the quote ---
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

        return HttpResponse("Sales order created successfully", status=201)

    except Exception as e:
        print("ADD SALES ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_sales_orders(request):
    orders = SalesOrder.objects.select_related(
        "owner", "customer", "quote", "deal",
        "billing_address", "shipping_address"
    ).prefetch_related("items__product").all().order_by("-updated_at")

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
        SalesOrder.objects.select_related(
            "owner", "customer", "quote", "deal",
            "billing_address", "shipping_address"
        ).prefetch_related("items__product"),
        id=id
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
        order = SalesOrder.objects.get(id=id)
    except SalesOrder.DoesNotExist:
        return HttpResponse("Sales order not found", status=404)

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

        return HttpResponse("Sales order updated successfully", status=200)

    except Exception as e:
        print("UPDATE SALES ORDER ERROR:", str(e))
        return HttpResponse(str(e), status=500)


@api_view(['DELETE'])
def delete_sales_order(request, id):
    try:
        order = SalesOrder.objects.get(id=id)
        order.delete()
        return JsonResponse({"message": "Sales order deleted successfully"})
    except SalesOrder.DoesNotExist:
        return HttpResponse("Sales order not found", status=404)
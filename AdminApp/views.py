from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view
from django.db.models import Sum
from django.db.models.functions import TruncWeek
from django.db.models import Count


from AdminApp.models import Customer, Deal, Lead, Staff, Task

# ..............lead.......................
@api_view(['POST'])
def add_lead(request):
    full_name = request.data.get("full_name")
    phone_number = request.data.get("phone_number")
    email = request.data.get("email")
    company_name = request.data.get("company_name")
    lead_source = request.data.get("lead_source")
    # assigned_to = request.data.get("assigned_to")
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
            # assigned_to_id=assigned_to,
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
                "assignedTo": str(i.assigned_to) if i.assigned_to else "—",
                "status": i.get_status_display(),
                "priority": i.priority,
                "description": i.lead_description,
                "dateAdded": i.created_at.strftime("%b %d, %Y") if i.created_at else "—",
                "createdAt": i.created_at.isoformat() if i.created_at else None,
            }
        )
    return JsonResponse(list, safe=False)
    


@api_view(['PUT'])
def update_lead(request, id):
    print("UPDATE DATA:", request.data)
    try:
        lead = Lead.objects.get(id=id)
    except Lead.DoesNotExist:
        print("UPDATE ERROR:", str(e))
        return HttpResponse("Lead not found", status=404)

    lead.full_name = request.data.get("full_name") or lead.full_name
    lead.phone_number = request.data.get("phone_number") or lead.phone_number
    lead.email = request.data.get("email") or lead.email
    lead.company_name = request.data.get("company_name") or lead.company_name
    lead.lead_source = request.data.get("lead_source") or lead.lead_source
    lead.assigned_to = request.data.get("assigned_to") or lead.assigned_to
    lead.priority = request.data.get("priority") or lead.priority
    lead.status = request.data.get("status") or lead.status
    lead.expected_closing_date = request.data.get("expected_closing_date") or lead.expected_closing_date
    lead.lead_description = request.data.get("lead_description") or lead.lead_description

    try:
        lead.save()
        return HttpResponse("Lead updated successfully", status=200)
    except Exception as e:
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
            "assignedTo": str(i.assigned_to) if i.assigned_to else "—",
            "source": i.deal_source,
            "priority": i.priority,
            "description": i.deal_description,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
        })
    return JsonResponse(list, safe=False)



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
    deal.assigned_to = request.data.get("assigned_to") or deal.assigned_to
    deal.expected_close_date = request.data.get("expected_close_date") or deal.expected_close_date
    deal.deal_source = request.data.get("deal_source") or deal.deal_source
    deal.priority = request.data.get("priority") or deal.priority
    deal.deal_description = request.data.get("deal_description") or deal.deal_description

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
            "assignedTo": str(i.assigned_to) if i.assigned_to else "—",
            "relatedTo": i.related_to,
            "priority": i.priority,
            "status": i.status,
            "dueDate": str(i.due_date) if i.due_date else None,
            "createdAt": i.created_at.isoformat() if i.created_at else None,
        })

    return JsonResponse(data, safe=False)



@api_view(['PUT'])
def update_task(request, id):
    try:
        task = Task.objects.get(id=id)

    except Task.DoesNotExist:
        return HttpResponse("Task not found", status=404)

    task.title = request.data.get("title") or task.title
    task.description = request.data.get("description") or task.description
    task.assigned_to = request.data.get("assigned_to") or task.assigned_to
    task.related_to = request.data.get("related_to") or task.related_to
    task.priority = request.data.get("priority") or task.priority
    task.status = request.data.get("status") or task.status
    task.due_date = request.data.get("due_date") or task.due_date

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
@api_view(['GET'])
def report_view(request):

    total_leads = Lead.objects.count()
    total_deals = Deal.objects.count()
    total_customers = Customer.objects.count()
    total_tasks = Task.objects.count()
    total_staff = Staff.objects.count()
    active_customers = Customer.objects.filter(status="active").count()
    pending_tasks = Task.objects.filter(status="pending").count()
    completed_tasks = Task.objects.filter(status="completed").count()
    high_priority_tasks = Task.objects.filter(priority="high").count()
    total_revenue = Customer.objects.aggregate(total=Sum("lifetime_value"))["total"] or 0

    # Revenue grouped by week
    revenue_over_time_qs = (
        Customer.objects
        .annotate(week=TruncWeek("created_at"))
        .values("week")
        .annotate(total=Sum("lifetime_value"))
        .order_by("week")
    )

    revenue_over_time = [
        {
            "date": entry["week"].strftime("%b %d"),
            "revenue": float(entry["total"] or 0),
        }
        for entry in revenue_over_time_qs
    ]

    # Leads grouped by status
    leads_by_status_qs = (
        Lead.objects
        .values("status")
        .annotate(count=Count("id"))
    )
    leads_by_status = {entry["status"]: entry["count"] for entry in leads_by_status_qs}

    # Deals grouped by stage
    deals_by_stage_qs = (
        Deal.objects
        .values("stage")
        .annotate(count=Count("id"))
    )
    deals_by_stage = {entry["stage"]: entry["count"] for entry in deals_by_stage_qs}

    # Leads grouped by source
    leads_by_source_qs = (
        Lead.objects
        .values("lead_source")
        .annotate(count=Count("id"))
    )
    leads_by_source = {entry["lead_source"]: entry["count"] for entry in leads_by_source_qs}

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
    }

    return JsonResponse(report)


# ......... convert lead to deal through button ...........
@api_view(['GET'])
def convert_lead_to_deal(request, lead_id):
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    if lead.status == "converted":
        return HttpResponse("Lead already converted", status=400)

    prefilled_data = {
        "deal_name": f"{lead.company_name} Deal",
        "company_name": lead.company_name,
        "deal_source": lead.lead_source,
        "priority": lead.priority,
        "assigned_to": lead.assigned_to_id,
        "expected_close_date": lead.expected_closing_date,
        "lead_id": lead.id,
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
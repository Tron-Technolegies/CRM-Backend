from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view


from AdminApp.models import Lead


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
            assigned_to=assigned_to,
            priority=priority,
            expected_closing_date=expected_closing_date,
            lead_description=lead_description,
        )

        return HttpResponse("Lead created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)


@api_view(['GET'])
def view_leads(request):
    leads = Lead.objects.all()
    list = []

    for i in leads:
        list.append(
            {
                "id": i.id,
                "name": i.full_name,
                "ph_number": i.phone_number,
                "email": i.email,
                "comp_name": i.company_name,
                "lead_src": i.lead_source,
                "assigned_to": i.assigned_to,
                "priority": i.priority,
                "exp_closing_date": i.expected_closing_date,
                "lead_dcr": i.lead_description,
                "created_at": i.created_at,
                "updated_at": i.updated_at
            }
        )
    return JsonResponse(list, safe=False)
    

@api_view(['PUT'])
def update_lead(request, id):
    try:
        lead = Lead.objects.get(id=id)
    except Lead.DoesNotExist:
        return HttpResponse("Lead not found", status=404)

    lead.full_name = request.data.get("full_name", lead.full_name)
    lead.phone_number = request.data.get("phone_number", lead.phone_number)
    lead.email = request.data.get("email", lead.email)
    lead.company_name = request.data.get("company_name", lead.company_name)
    lead.lead_source = request.data.get("lead_source", lead.lead_source)
    lead.assigned_to = request.data.get("assigned_to", lead.assigned_to)
    lead.priority = request.data.get("priority", lead.priority)
    lead.expected_closing_date = request.data.get("expected_closing_date",lead.expected_closing_date)
    lead.lead_description = request.data.get("lead_description", lead.lead_description)

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
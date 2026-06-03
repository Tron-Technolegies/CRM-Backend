from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view


from AdminApp.models import Deal, Lead

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

    lead.full_name = request.data.get("full_name") or lead.full_name
    lead.phone_number = request.data.get("phone_number") or lead.phone_number
    lead.email = request.data.get("email") or lead.email
    lead.company_name = request.data.get("company_name") or lead.company_name
    lead.lead_source = request.data.get("lead_source") or lead.lead_source
    lead.assigned_to = request.data.get("assigned_to") or lead.assigned_to
    lead.priority = request.data.get("priority") or lead.priority
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

    if not deal_name or not company_name:
        return HttpResponse(
            "Deal name and company name are mandatory fields",
            status=400
        )

    try:
        Deal.objects.create(
            deal_name=deal_name,
            company_name=company_name,
            deal_amount=deal_amount,
            stage=stage,
            assigned_to=assigned_to,
            expected_close_date=expected_close_date,
            deal_source=deal_source,
            priority=priority,
            deal_description=deal_description,
        )

        return HttpResponse("Deal created successfully", status=201)

    except Exception as e:
        return HttpResponse(str(e), status=500)
    


@api_view(['GET'])
def view_deals(request):
    deals = Deal.objects.all()
    list = []

    for i in deals:
        list.append(
            {
                "id": i.id,
                "deal_name": i.deal_name,
                "company_name": i.company_name,
                "deal_amount": i.deal_amount,
                "stage": i.stage,
                "assigned_to": i.assigned_to,
                "expected_close_date": i.expected_close_date,
                "deal_source": i.deal_source,
                "priority": i.priority,
                "deal_description": i.deal_description,
                "created_at": i.created_at,
                "updated_at": i.updated_at
            }
        )
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

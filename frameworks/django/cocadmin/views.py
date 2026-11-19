import os
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_POST
from coc import Client

def broker():
    return Client(os.environ.get("COC_URL","http://127.0.0.1:7310"),os.environ["COC_ADMIN_TOKEN"],os.environ.get("COC_ADMIN_AGENT","django-admin"))

@staff_member_required
def overview(request):
    try: state, error = broker().call("COC.DISCOVER", {"view":"system"}), None
    except Exception: state, error = None, "Broker unavailable or administration credential rejected."
    return render(request,"overview.html",{"state":state,"error":error})

@staff_member_required
def snapshot(request):
    try: return JsonResponse(broker().call("COC.DISCOVER",{"view":"system"}))
    except Exception: return JsonResponse({"error":"broker unavailable"},status=503)

@staff_member_required
@require_POST
def control(request):
    if not request.user.has_perm("cocadmin.control_broker"): return HttpResponseForbidden()
    method={"cancel":"COC.CANCEL","retry":"COC.RECOVER"}.get(request.POST.get("action"))
    if not method:return JsonResponse({"error":"unsupported control"},status=400)
    payload={"task_id":request.POST.get("task_id","")}
    if method=="COC.RECOVER":payload["action"]="retry"
    try:
        result=broker().call(method,payload)
        broker().call("COC.EVENT",{"kind":"administration_action","operator":str(request.user.pk),"task_id":payload["task_id"],"action":request.POST["action"]})
        return JsonResponse(result)
    except Exception:return JsonResponse({"error":"operation rejected; inspect broker task state"},status=409)

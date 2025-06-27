from django.shortcuts import render, redirect
from ecommerceapp.models import Contact, Product, OrderUpdate, Orders
from django.contrib import messages
from math import ceil
from ecommerceapp import keys
from django.views.decorators.csrf import csrf_exempt
from PayTm import Checksum
import json

MERCHANT_KEY = keys.MK

def index(request):
    allProds = []
    catprods = Product.objects.values('category', 'id')
    cats = {item['category'] for item in catprods}
    for cat in cats:
        prod = Product.objects.filter(category=cat)
        n = len(prod)
        nSlides = n // 4 + ceil((n / 4) - (n // 4))
        allProds.append([prod, range(1, nSlides), nSlides])
    params = {'allProds': allProds}
    return render(request, "index.html", params)

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        desc = request.POST.get("desc")
        pnumber = request.POST.get("pnumber")
        myquery = Contact(name=name, email=email, desc=desc, phonenumber=pnumber)
        myquery.save()
        messages.info(request, "We will get back to you soon.")
        return render(request, "contact.html")
    return render(request, "contact.html")

def about(request):
    return render(request, "about.html")

def checkout(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Login & Try Again")
        return redirect('/auth/login')

    if request.method == "POST":
        items_json = request.POST.get('itemsJson', '')
        name = request.POST.get('name', '')
        amount = request.POST.get('amt')
        email = request.POST.get('email', '')
        address1 = request.POST.get('address1', '')
        address2 = request.POST.get('address2', '')
        city = request.POST.get('city', '')
        state = request.POST.get('state', '')
        zip_code = request.POST.get('zip_code', '')
        phone = request.POST.get('phone', '')

        order = Orders(
            items_json=items_json,
            name=name,
            amount=amount,
            email=email,
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone
        )
        order.save()

        order.oid = f"{order.pk}ShopyCart"
        order.save()

        update = OrderUpdate(order_id=order.oid, update_desc="The order has been placed")
        update.save()

        param_dict = {
            'MID': keys.MID,
            'ORDER_ID': order.oid,
            'TXN_AMOUNT': str(amount),
            'CUST_ID': email,
            'INDUSTRY_TYPE_ID': 'Retail',
            'WEBSITE': 'WEBSTAGING',
            'CHANNEL_ID': 'WEB',
            'CALLBACK_URL': 'http://127.0.0.1:8000/handlerequest/',
        }

        try:
            param_dict['CHECKSUMHASH'] = Checksum.generate_checksum(param_dict, MERCHANT_KEY)
        except Exception as e:
            print("Checksum generation failed:", e)
            messages.error(request, "Payment gateway error. Please try again.")
            return redirect('/checkout/')

        return render(request, 'paytm.html', {'param_dict': param_dict})

    return render(request, 'checkout.html')

@csrf_exempt
def handlerequest(request):
    form = request.POST
    response_dict = {}
    checksum = form.get('CHECKSUMHASH')

    for key in form.keys():
        response_dict[key] = form[key]

    if not checksum:
        print("Missing checksum in response.")
        return render(request, 'paymentstatus.html', {'response': response_dict, 'error': 'Missing checksum'})

    try:
        verify = Checksum.verify_checksum(response_dict, MERCHANT_KEY, checksum)
    except Exception as e:
        print("Checksum verification failed:", e)
        return render(request, 'paymentstatus.html', {'response': response_dict, 'error': str(e)})

    if verify:
        if response_dict.get('RESPCODE') == '01':
            print('Order successful')
            full_order_id = response_dict['ORDERID']
            paid_amount = response_dict['TXNAMOUNT']
            actual_id = full_order_id.replace("ShopyCart", "")

            try:
                order = Orders.objects.get(pk=int(actual_id))
                order.oid = full_order_id
                order.amountpaid = paid_amount
                order.paymentstatus = "PAID"
                order.save()
            except Orders.DoesNotExist:
                print("Order not found for ID:", actual_id)
        else:
            print(f"Order failed: {response_dict.get('RESPMSG')}")
    else:
        print("Checksum verification failed")

    return render(request, 'paymentstatus.html', {'response': response_dict})

def profile(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Login & Try Again")
        return redirect('/auth/login')

    currentuser = request.user.username
    items = Orders.objects.filter(email=currentuser)

    for order in items:
        try:
            order.item_details = json.loads(order.items_json)
        except Exception as e:
            order.item_details = {}

        if order.oid:
            order.status_updates = OrderUpdate.objects.filter(order_id=order.oid)
        else:
            order.status_updates = []

    context = {"items": items}
    return render(request, "profile.html", context)

    if not request.user.is_authenticated:
        messages.warning(request, "Login & Try Again")
        return redirect('/auth/login')

    currentuser = request.user.username
    items = Orders.objects.filter(email=currentuser)

    for order in items:
        order.status_updates = OrderUpdate.objects.filter(order_id=order.oid)
        try:
            order.items_parsed = json.loads(order.items_json)
        except json.JSONDecodeError:
            order.items_parsed = {}

    context = {"items": items}
    return render(request, "profile.html", context)

    if not request.user.is_authenticated:
        messages.warning(request, "Login & Try Again")
        return redirect('/auth/login')

    currentuser = request.user.username
    items = Orders.objects.filter(email=currentuser)

    for order in items:
        if order.oid:
            order.status_updates = OrderUpdate.objects.filter(order_id=order.oid)

    context = {"items": items}
    return render(request, "profile.html", context)


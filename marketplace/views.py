from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.shortcuts import render, redirect
from .models import User, CropListing, Order, CropAdvisory
from .forms import CropListingForm, CropAdvisoryForm, OrderForm


GRADE_RATE_MULTIPLIERS = {
    'GRADE_A': Decimal('1.10'),
    'GRADE_B': Decimal('1.00'),
    'GRADE_C': Decimal('0.90'),
}

MANDI_MULTIPLIERS = {
    'pune': Decimal('1.05'),
    'mumbai': Decimal('1.12'),
    'delhi': Decimal('1.22'),
}

LOW_STOCK_THRESHOLD = Decimal('50')


def _get_logged_in_farmer(request):
    farmer_id = request.session.get('farmer_id')
    if farmer_id:
        return User.objects.filter(id=farmer_id, role='FARMER').first()
    return None


def _get_logged_in_buyer(request):
    buyer_id = request.session.get('buyer_id')
    if buyer_id:
        return User.objects.filter(id=buyer_id, role='BUYER').first()
    return None


def _restore_stock_on_cancellation(order):
    listing = CropListing.objects.select_for_update().get(id=order.listing.id)
    current_qty = Decimal(str(listing.quantity_available or 0))
    restored_qty = Decimal(str(order.quantity or 0))
    listing.quantity_available = current_qty + restored_qty
    if listing.quantity_available > 0 and listing.status == 'SOLD_OUT':
        listing.status = 'AVAILABLE'
    listing.save()


def home(request):
    listings = CropListing.objects.select_related('farmer').order_by('-id')
    orders = Order.objects.select_related('buyer', 'listing').order_by('-id')
    advisories = CropAdvisory.objects.order_by('-id')
    farmers = User.objects.filter(role='FARMER').order_by('full_name')
    buyers = User.objects.filter(role='BUYER').order_by('full_name')

    logged_in_farmer = _get_logged_in_farmer(request)
    logged_in_buyer = _get_logged_in_buyer(request)

    farmer_listings_count = 0
    farmer_orders_count = 0
    if logged_in_farmer:
        farmer_listings_count = listings.filter(farmer=logged_in_farmer).count()
        farmer_orders_count = orders.filter(listing__farmer=logged_in_farmer).count()

    buyer_orders_count = 0
    if logged_in_buyer:
        buyer_orders_count = orders.filter(buyer=logged_in_buyer).count()

    context = {
        'active_page': 'home',
        'listings_count': listings.count(),
        'available_listings_count': listings.filter(status='AVAILABLE').count(),
        'orders_count': orders.count(),
        'advisories_count': advisories.count(),
        'farmers_count': farmers.count(),
        'buyers_count': buyers.count(),
        'logged_in_farmer': logged_in_farmer,
        'logged_in_buyer': logged_in_buyer,
        'farmer_listings_count': farmer_listings_count,
        'farmer_orders_count': farmer_orders_count,
        'buyer_orders_count': buyer_orders_count,
    }
    return render(request, 'marketplace/home.html', context)


def available_products(request):
    crop_query = request.GET.get('crop', '').strip()
    category_query = request.GET.get('category', '').strip()
    farming_query = request.GET.get('farming_type', '').strip()
    grade_query = request.GET.get('quality_grade', '').strip()

    listings = CropListing.objects.select_related('farmer').order_by('-id')
    if crop_query:
        listings = listings.filter(crop_name__icontains=crop_query)
    if category_query:
        listings = listings.filter(category__icontains=category_query)
    if farming_query:
        listings = listings.filter(farming_type=farming_query)
    if grade_query:
        listings = listings.filter(quality_grade=grade_query)

    context = {
        'active_page': 'products',
        'listings': listings,
        'crop_query': crop_query,
        'category_query': category_query,
        'farming_query': farming_query,
        'grade_query': grade_query,
        'farming_choices': CropListing.FARMING_TYPE_CHOICES,
        'grade_choices': CropListing.QUALITY_GRADE_CHOICES,
        'logged_in_buyer': _get_logged_in_buyer(request),
    }
    return render(request, 'marketplace/products.html', context)


def market_rates(request):
    crop_query = request.GET.get('crop', '').strip()
    category_query = request.GET.get('category', '').strip()

    listings = CropListing.objects.select_related('farmer').order_by('-id')
    if crop_query:
        listings = listings.filter(crop_name__icontains=crop_query)
    if category_query:
        listings = listings.filter(category__icontains=category_query)

    rows = []
    for item in listings:
        base_rate = Decimal(str(item.price_per_unit or 0))
        grade_mult = GRADE_RATE_MULTIPLIERS.get(item.quality_grade, Decimal('1.00'))
        quality_rate = (base_rate * grade_mult).quantize(Decimal('0.01'))
        unit = item.unit or 'kg'

        rows.append({
            'item': item,
            'unit': unit,
            'quality_rate': quality_rate,
            'pune_rate': (quality_rate * MANDI_MULTIPLIERS['pune']).quantize(Decimal('0.01')),
            'mumbai_rate': (quality_rate * MANDI_MULTIPLIERS['mumbai']).quantize(Decimal('0.01')),
            'delhi_rate': (quality_rate * MANDI_MULTIPLIERS['delhi']).quantize(Decimal('0.01')),
        })

    context = {
        'active_page': 'rates',
        'rows': rows,
        'crop_query': crop_query,
        'category_query': category_query,
    }
    return render(request, 'marketplace/market_rates.html', context)


def forms_hub(request):
    logged_in_buyer = _get_logged_in_buyer(request)
    initial_order = {'buyer': logged_in_buyer.id} if logged_in_buyer else {}

    listing_form = CropListingForm(
        initial={
            'unit': 'kg',
            'status': 'AVAILABLE',
            'farming_type': 'ORGANIC',
            'quality_grade': 'GRADE_A',
        }
    )
    advisory_form = CropAdvisoryForm()
    order_form = OrderForm(initial=initial_order)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'crop_listing':
            listing_form = CropListingForm(request.POST)
            if listing_form.is_valid():
                listing = listing_form.save(commit=False)
                if not listing.status:
                    listing.status = 'AVAILABLE'
                listing.save()
                request.session['flash_msg'] = 'Crop listing saved to MySQL!'
                return redirect('forms_hub')

        elif form_type == 'order':
            order_form = OrderForm(request.POST)
            if order_form.is_valid():
                order = order_form.save(commit=False)
                qty = Decimal(str(order.quantity))

                with transaction.atomic():
                    listing = CropListing.objects.select_for_update().get(id=order.listing.id)
                    available = Decimal(str(listing.quantity_available or 0))
                    rate = Decimal(str(listing.price_per_unit or 0))

                    if qty <= 0:
                        order_form.add_error('quantity', 'Quantity must be greater than 0.')
                    elif qty > available:
                        order_form.add_error(
                            'quantity',
                            f'Only {available} {listing.unit or "kg"} available in stock.',
                        )
                    else:
                        listing.quantity_available = available - qty
                        if listing.quantity_available == 0:
                            listing.status = 'SOLD_OUT'
                        listing.save()

                        order.listing = listing
                        order.total_amount = (qty * rate).quantize(Decimal('0.01'))
                        if not order.status:
                            order.status = 'PENDING'
                        order.save()
                        request.session['flash_msg'] = 'Order placed and stock updated in MySQL!'
                        return redirect('buyer_login' if logged_in_buyer else 'orders_status')

        elif form_type == 'crop_advisory':
            advisory_form = CropAdvisoryForm(request.POST)
            if advisory_form.is_valid():
                advisory_form.save()
                request.session['flash_msg'] = 'Crop advisory saved to MySQL!'
                return redirect('forms_hub')

    saved_message = request.session.pop('flash_msg', None)

    context = {
        'active_page': 'forms',
        'listing_form': listing_form,
        'advisory_form': advisory_form,
        'order_form': order_form,
        'saved_message': saved_message,
        'logged_in_buyer': logged_in_buyer,
    }
    return render(request, 'marketplace/forms_page.html', context)


def orders_status(request):
    logged_in_farmer = _get_logged_in_farmer(request)
    logged_in_buyer = _get_logged_in_buyer(request)

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        valid_statuses = dict(Order.STATUS_CHOICES).keys()

        if order_id and new_status in valid_statuses:
            with transaction.atomic():
                order = Order.objects.select_for_update().select_related('listing').get(id=order_id)
                old_status = order.status

                if old_status != 'CANCELLED' and new_status == 'CANCELLED':
                    _restore_stock_on_cancellation(order)

                order.status = new_status
                order.save()
                request.session['flash_msg'] = f'Order #{order.id} status updated to {new_status}.'

        return redirect(request.META.get('HTTP_REFERER') or 'orders_status')

    saved_message = request.session.pop('flash_msg', None)
    orders = Order.objects.select_related('buyer', 'listing', 'listing__farmer').order_by('-id')
    if logged_in_buyer and not logged_in_farmer:
        orders = orders.filter(buyer=logged_in_buyer)

    context = {
        'active_page': 'orders',
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'saved_message': saved_message,
        'logged_in_farmer': logged_in_farmer,
        'logged_in_buyer': logged_in_buyer,
    }
    return render(request, 'marketplace/orders.html', context)


def crop_advisory(request):
    season_query = request.GET.get('season', '').strip()
    crop_query = request.GET.get('crop', '').strip()
    saved_message = request.session.pop('flash_msg', None)
    error_message = None

    if request.method == 'POST' and request.POST.get('action') == 'add_advisory':
        advisory_title = request.POST.get('advisory_title', '').strip()
        crop_name = request.POST.get('crop_name', '').strip()
        season = request.POST.get('season', '').strip()
        issue_keyword = request.POST.get('issue_keyword', '').strip()
        guidance_text = request.POST.get('guidance_text', '').strip()

        if not advisory_title or not crop_name or not guidance_text:
            error_message = 'Please fill Advisory Title, Crop Name, and Guidance.'
        else:
            CropAdvisory.objects.create(
                advisory_title=advisory_title,
                crop_name=crop_name,
                season=season or 'General',
                issue_keyword=issue_keyword or 'General Care',
                guidance_text=guidance_text,
            )
            request.session['flash_msg'] = 'New crop advisory published!'
            return redirect('crop_advisory')

    advisories = CropAdvisory.objects.order_by('-id')
    if season_query:
        advisories = advisories.filter(season__icontains=season_query)
    if crop_query:
        advisories = advisories.filter(crop_name__icontains=crop_query)

    context = {
        'active_page': 'advisory',
        'advisories': advisories,
        'season_query': season_query,
        'crop_query': crop_query,
        'saved_message': saved_message,
        'error_message': error_message,
        'logged_in_farmer': _get_logged_in_farmer(request),
    }
    return render(request, 'marketplace/advisory.html', context)


def farmer_login(request):
    error_message = None
    saved_message = request.session.pop('flash_msg', None)
    logged_in_farmer = _get_logged_in_farmer(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'logout':
            request.session.pop('farmer_id', None)
            return redirect('farmer_login')

        elif action == 'register_farmer':
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            location = request.POST.get('location', '').strip()
            password_input = request.POST.get('password', '').strip() or '1234'

            if not full_name or not phone:
                error_message = 'Please enter Full Name and Phone Number to register.'
            elif User.objects.filter(phone=phone).exists():
                error_message = 'This phone number is already registered. Please log in.'
            else:
                new_farmer = User.objects.create(
                    full_name=full_name,
                    phone=phone,
                    role='FARMER',
                    location=location or 'Sangola',
                    password_hash=password_input,
                )
                request.session.pop('buyer_id', None)
                request.session['farmer_id'] = new_farmer.id
                request.session['flash_msg'] = f'Welcome, {new_farmer.full_name}! Your farmer account is ready.'
                return redirect('farmer_login')

        elif action == 'add_crop' and logged_in_farmer:
            crop_name = request.POST.get('crop_name', '').strip()
            category = request.POST.get('category', '').strip()
            farming_type = request.POST.get('farming_type', 'ORGANIC').strip() or 'ORGANIC'
            quality_grade = request.POST.get('quality_grade', 'GRADE_A').strip() or 'GRADE_A'
            price_per_unit = request.POST.get('price_per_unit', '').strip()
            quantity_available = request.POST.get('quantity_available', '').strip()
            unit = request.POST.get('unit', 'kg').strip() or 'kg'
            status = request.POST.get('status', 'AVAILABLE').strip() or 'AVAILABLE'

            if not crop_name or not price_per_unit or not quantity_available:
                error_message = 'Please fill Crop Name, Price per Unit, and Available Quantity.'
            else:
                try:
                    price_val = Decimal(price_per_unit)
                    qty_val = Decimal(quantity_available)
                    if price_val <= 0 or qty_val <= 0:
                        error_message = 'Price and Quantity must be greater than 0.'
                    else:
                        CropListing.objects.create(
                            farmer=logged_in_farmer,
                            crop_name=crop_name,
                            category=category or 'General',
                            farming_type=farming_type,
                            quality_grade=quality_grade,
                            price_per_unit=price_val,
                            quantity_available=qty_val,
                            unit=unit,
                            status=status,
                        )
                        request.session['flash_msg'] = f'"{crop_name}" added to your listings!'
                        return redirect('farmer_login')
                except (InvalidOperation, ValueError):
                    error_message = 'Enter valid numeric values for Price and Quantity.'

        elif action == 'update_order_status' and logged_in_farmer:
            order_id = request.POST.get('order_id')
            new_status = request.POST.get('status')
            valid_statuses = dict(Order.STATUS_CHOICES).keys()

            if order_id and new_status in valid_statuses:
                with transaction.atomic():
                    order = (
                        Order.objects.select_for_update()
                        .select_related('listing')
                        .filter(id=order_id, listing__farmer=logged_in_farmer)
                        .first()
                    )
                    if order:
                        old_status = order.status
                        if old_status != 'CANCELLED' and new_status == 'CANCELLED':
                            _restore_stock_on_cancellation(order)

                        order.status = new_status
                        order.save()
                        request.session['flash_msg'] = f'Order #{order.id} updated to {new_status}.'
            return redirect('farmer_login')

        elif action == 'add_advisory' and logged_in_farmer:
            advisory_title = request.POST.get('advisory_title', '').strip()
            crop_name = request.POST.get('crop_name', '').strip()
            season = request.POST.get('season', '').strip()
            issue_keyword = request.POST.get('issue_keyword', '').strip()
            guidance_text = request.POST.get('guidance_text', '').strip()

            if not advisory_title or not crop_name or not guidance_text:
                error_message = 'Please fill Advisory Title, Crop Name, and Guidance.'
            else:
                CropAdvisory.objects.create(
                    advisory_title=advisory_title,
                    crop_name=crop_name,
                    season=season or 'General',
                    issue_keyword=issue_keyword or 'General Care',
                    guidance_text=guidance_text,
                )
                request.session['flash_msg'] = f'Crop advisory for "{crop_name}" added!'
                return redirect('farmer_login')

        else:
            phone = request.POST.get('phone', '').strip()
            password_input = request.POST.get('password', '').strip()

            farmer = User.objects.filter(phone=phone, role='FARMER').first()
            if not farmer:
                error_message = 'Farmer account not found for this phone number.'
            else:
                stored_pwd = (farmer.password_hash or '').strip()
                valid_demo_passwords = {stored_pwd, '1234', 'demo123'} - {''}
                if password_input in valid_demo_passwords:
                    request.session.pop('buyer_id', None)
                    request.session['farmer_id'] = farmer.id
                    return redirect('farmer_login')
                else:
                    error_message = 'Invalid password/PIN. Try 1234 or your account password.'

    farmer_listings = []
    incoming_orders = []
    total_earnings = Decimal('0.00')
    pending_orders_count = 0
    low_stock_count = 0

    if logged_in_farmer:
        farmer_listings = list(CropListing.objects.filter(farmer=logged_in_farmer).order_by('-id'))
        incoming_orders = list(
            Order.objects.select_related('buyer', 'listing')
            .filter(listing__farmer=logged_in_farmer)
            .order_by('-id')
        )

        active_orders = [ord_item for ord_item in incoming_orders if ord_item.status != 'CANCELLED']
        total_earnings = sum(
            (Decimal(str(ord_item.total_amount or 0)) for ord_item in active_orders),
            Decimal('0.00'),
        ).quantize(Decimal('0.01'))

        pending_orders_count = sum(1 for ord_item in incoming_orders if ord_item.status == 'PENDING')

        for item in farmer_listings:
            qty = Decimal(str(item.quantity_available or 0))
            is_low = Decimal('0') < qty <= LOW_STOCK_THRESHOLD
            item.is_low_stock = is_low
            if is_low:
                low_stock_count += 1

    advisories = CropAdvisory.objects.order_by('-id')
    farmers_list = User.objects.filter(role='FARMER').order_by('full_name')

    context = {
        'active_page': 'farmer_login',
        'logged_in_farmer': logged_in_farmer,
        'farmer_listings': farmer_listings,
        'incoming_orders': incoming_orders,
        'status_choices': Order.STATUS_CHOICES,
        'farming_choices': CropListing.FARMING_TYPE_CHOICES,
        'grade_choices': CropListing.QUALITY_GRADE_CHOICES,
        'advisories': advisories,
        'farmers_list': farmers_list,
        'error_message': error_message,
        'saved_message': saved_message,
        'total_earnings': total_earnings,
        'pending_orders_count': pending_orders_count,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'marketplace/farmer_login.html', context)


def buyer_login(request):
    error_message = None
    saved_message = request.session.pop('flash_msg', None)
    logged_in_buyer = _get_logged_in_buyer(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'logout':
            request.session.pop('buyer_id', None)
            return redirect('buyer_login')

        elif action == 'register_buyer':
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            location = request.POST.get('location', '').strip()
            password_input = request.POST.get('password', '').strip() or '1234'

            if not full_name or not phone:
                error_message = 'Please enter Full Name and Phone Number to register.'
            elif User.objects.filter(phone=phone).exists():
                error_message = 'This phone number is already registered. Please log in.'
            else:
                new_buyer = User.objects.create(
                    full_name=full_name,
                    phone=phone,
                    role='BUYER',
                    location=location or 'Pune',
                    password_hash=password_input,
                )
                request.session.pop('farmer_id', None)
                request.session['buyer_id'] = new_buyer.id
                request.session['flash_msg'] = f'Welcome, {new_buyer.full_name}! Your buyer account is ready.'
                return redirect('buyer_login')

        else:
            phone = request.POST.get('phone', '').strip()
            password_input = request.POST.get('password', '').strip()

            buyer = User.objects.filter(phone=phone, role='BUYER').first()
            if not buyer:
                error_message = 'Buyer account not found for this phone number.'
            else:
                stored_pwd = (buyer.password_hash or '').strip()
                valid_demo_passwords = {stored_pwd, '1234', 'demo123'} - {''}
                if password_input in valid_demo_passwords:
                    request.session.pop('farmer_id', None)
                    request.session['buyer_id'] = buyer.id
                    return redirect('buyer_login')
                else:
                    error_message = 'Invalid password/PIN. Try 1234 or your account password.'

    buyer_orders = []
    if logged_in_buyer:
        buyer_orders = (
            Order.objects.select_related('listing', 'listing__farmer')
            .filter(buyer=logged_in_buyer)
            .order_by('-id')
        )

    available_listings = (
        CropListing.objects.select_related('farmer')
        .filter(status='AVAILABLE', quantity_available__gt=0)
        .order_by('-id')
    )
    buyers_list = User.objects.filter(role='BUYER').order_by('full_name')

    context = {
        'active_page': 'buyer_login',
        'logged_in_buyer': logged_in_buyer,
        'buyer_orders': buyer_orders,
        'available_listings': available_listings,
        'buyers_list': buyers_list,
        'error_message': error_message,
        'saved_message': saved_message,
    }
    return render(request, 'marketplace/buyer_login.html', context)


def buyer_contacts(request):
    buyers = User.objects.filter(role='BUYER').prefetch_related('orders__listing').order_by('full_name')
    context = {
        'active_page': 'buyers',
        'buyers': buyers,
    }
    return render(request, 'marketplace/buyers.html', context)
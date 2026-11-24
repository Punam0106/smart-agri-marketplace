from django.db import models


class User(models.Model):
    ROLE_CHOICES = [
        ('FARMER', 'Farmer'),
        ('BUYER', 'Buyer'),
    ]

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    location = models.CharField(max_length=120, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class CropListing(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('SOLD_OUT', 'Sold Out'),
    ]

    FARMING_TYPE_CHOICES = [
        ('ORGANIC', 'Organic'),
        ('INORGANIC', 'Inorganic'),
    ]

    QUALITY_GRADE_CHOICES = [
        ('GRADE_A', 'Grade A (Premium)'),
        ('GRADE_B', 'Grade B (Standard)'),
        ('GRADE_C', 'Grade C (Economy)'),
    ]

    farmer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='crop_listings',
        limit_choices_to={'role': 'FARMER'},
    )
    crop_name = models.CharField(max_length=100)
    category = models.CharField(max_length=80, blank=True, null=True)
    farming_type = models.CharField(
        max_length=20,
        choices=FARMING_TYPE_CHOICES,
        default='ORGANIC',
    )
    quality_grade = models.CharField(
        max_length=20,
        choices=QUALITY_GRADE_CHOICES,
        default='GRADE_A',
    )
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, default='kg')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    def __str__(self):
        return f"{self.crop_name} ({self.get_farming_type_display()} - {self.get_quality_grade_display()})"


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending / Waiting'),
        ('CONFIRMED', 'Confirmed'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders',
        limit_choices_to={'role': 'BUYER'},
    )
    listing = models.ForeignKey(
        CropListing,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.listing.crop_name} ({self.status})"


class CropAdvisory(models.Model):
    advisory_title = models.CharField(max_length=160)
    crop_name = models.CharField(max_length=100)
    season = models.CharField(max_length=60, blank=True, null=True)
    issue_keyword = models.CharField(max_length=100, blank=True, null=True)
    guidance_text = models.TextField()

    def __str__(self):
        return f"{self.advisory_title} ({self.crop_name})"
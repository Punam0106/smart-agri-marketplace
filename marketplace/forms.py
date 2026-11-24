from django import forms
from .models import CropListing, CropAdvisory, Order


class CropListingForm(forms.ModelForm):
    class Meta:
        model = CropListing
        fields = [
            'farmer',
            'crop_name',
            'category',
            'farming_type',
            'quality_grade',
            'price_per_unit',
            'quantity_available',
            'unit',
            'status',
        ]


class CropAdvisoryForm(forms.ModelForm):
    class Meta:
        model = CropAdvisory
        fields = [
            'advisory_title',
            'crop_name',
            'season',
            'issue_keyword',
            'guidance_text',
        ]


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'buyer',
            'listing',
            'quantity',
        ]
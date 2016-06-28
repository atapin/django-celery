from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as StockUserAdmin
from django.contrib.auth.models import User

from .models import Customer

# Register your models here.


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    exclude = ('customer_email', 'customer_first_name', 'customer_last_name')
    verbose_name = 'CRM customer name'

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(StockUserAdmin):
    inlines = (CustomerInline, )
    fieldsets = (
        ('Personal info', {
            'fields': ('username', 'password', 'first_name', 'last_name', 'email', 'is_active', 'is_staff')
        }),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    This admin module is for managing CRM-only customer databases
    e.g. potential customers.
    """
    list_display = ('full_name', 'country', 'email', 'date_arrived')

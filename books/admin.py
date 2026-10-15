from datetime import date
from django.contrib import admin
from .models import Category, Book, Member, BorrowRecord, Review, Reservation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn', 'category', 'total_copies', 'available_copies', 'waitlist_count')
    list_filter = ('category', 'published_year')
    search_fields = ('title', 'author', 'isbn')

    def waitlist_count(self, obj):
        return obj.waitlist_count
    waitlist_count.short_description = 'Waitlist'


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'membership_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'phone')


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ('member', 'book', 'borrow_date', 'due_date', 'return_date', 'overdue_status', 'fine_amount')
    list_filter = ('status', 'borrow_date')
    search_fields = ('member__user__username', 'book__title')

    def overdue_status(self, obj):
        if obj.status == 'borrowed' and obj.due_date < date.today():
            return '⚠️ OVERDUE'
        return obj.status
    overdue_status.short_description = 'Status'

    def fine_amount(self, obj):
        return f"₹{obj.fine_amount}"
    fine_amount.short_description = 'Fine'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('member', 'book', 'reserved_on', 'status', 'position_display')
    list_filter = ('status', 'reserved_on')
    search_fields = ('member__user__username', 'book__title')

    def position_display(self, obj):
        pos = obj.position
        return f"#{pos}" if pos else '-'
    position_display.short_description = 'Position'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('book', 'member', 'rating', 'created_on')
    list_filter = ('rating', 'created_on')
    search_fields = ('book__title', 'member__user__username')

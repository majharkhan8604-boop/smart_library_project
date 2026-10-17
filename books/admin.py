from datetime import date
from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Category, Book, Member, BorrowRecord, Review, Reservation
from .utils import fetch_cover_from_google_books, fetch_cover_from_openlibrary


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn', 'category', 'total_copies', 'available_copies', 'cover_preview', 'waitlist_count')
    list_filter = ('category', 'published_year')
    search_fields = ('title', 'author', 'isbn')
    actions = ['fetch_covers_action']

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height: 60px; border-radius: 4px;" />', obj.cover_image)
        return '❌ No cover'
    cover_preview.short_description = 'Cover'

    def waitlist_count(self, obj):
        return obj.waitlist_count
    waitlist_count.short_description = 'Waitlist'

    @admin.action(description='📸 Fetch covers (Google Books + Open Library)')
    def fetch_covers_action(self, request, queryset):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        books_to_fetch = [book for book in queryset if not book.cover_image]
        skipped = queryset.count() - len(books_to_fetch)

        if not books_to_fetch:
            self.message_user(request, "All selected books already have covers.", messages.WARNING)
            return

        def fetch_one(book):
            try:
                url = fetch_cover_from_google_books(book.isbn)
                if not url:
                    url = fetch_cover_from_openlibrary(book.isbn)

                if url:
                    book.cover_image = url
                    book.save(update_fields=['cover_image'])
                    return ('success', book.title)
                return ('failed', book.title)
            except Exception as e:
                return ('error', f"{book.title}: {e}")

        success = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_one, book): book for book in books_to_fetch}
            for future in as_completed(futures):
                status, _ = future.result()
                if status == 'success':
                    success += 1
                else:
                    failed += 1

        self.message_user(
            request,
            f"✅ Fetched: {success} | ⏭️ Skipped: {skipped} | ❌ Failed: {failed}",
            messages.SUCCESS
        )


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'library_card_number', 'phone', 'membership_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'library_card_number', 'phone')
    readonly_fields = ('library_card_number',)


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


# Admin panel branding
admin.site.site_header = 'Smart Library - Admin Panel'
admin.site.site_title = 'Smart Library'
admin.site.index_title = 'Welcome, Mazhar Hussain'

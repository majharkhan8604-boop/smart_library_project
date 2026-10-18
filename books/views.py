import csv
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Avg, Sum
from django.core.paginator import Paginator
from datetime import date, timedelta
from django.views.decorators.csrf import csrf_exempt
from .models import Book, Category, Member, BorrowRecord, Review, Reservation
from .utils import (
    send_due_reminder, send_overdue_notice, send_waitlist_ready, send_fine_reminder,
    chatbot_response
)



def home(request):
    featured_books = Book.objects.all().order_by('-added_on')[:100]
    categories = Category.objects.all()
    total_books = Book.objects.count()
    total_members = Member.objects.count()

    return render(request, 'books/home.html', {
        'featured_books': featured_books,
        'categories': categories,
        'total_books': total_books,
        'total_members': total_members,
    })
def book_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    books = Book.objects.all()

    if query:
        books = books.filter(Q(title__icontains=query) | Q(author__icontains=query))
    if category_id:
        books = books.filter(category_id=category_id)

    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()
    return render(request, 'books/book_list.html', {
        'books': page_obj,
        'page_obj': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })


def autocomplete_books(request):
    query = request.GET.get('q', '')
    results = []

    if query and len(query) >= 2:
        books = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )[:8]

        for book in books:
            results.append({
                'id': book.id,
                'title': book.title,
                'author': book.author,
                'available': book.is_available,
                'available_copies': book.available_copies,
            })

    return JsonResponse({'results': results})


def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    reviews = book.reviews.all().order_by('-created_on')

    user_reservation = None
    if request.user.is_authenticated:
        try:
            member = Member.objects.get(user=request.user)
            user_reservation = Reservation.objects.filter(
                member=member, book=book, status__in=['waiting', 'ready']
            ).first()
        except Member.DoesNotExist:
            pass

    return render(request, 'books/book_detail.html', {
        'book': book,
        'reviews': reviews,
        'user_reservation': user_reservation,
    })


@login_required
def borrow_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    if not book.is_available:
        messages.error(request, "This book is currently not available. You can join the waitlist.")
        return redirect('books:book_detail', book_id=book.id)

    member, created = Member.objects.get_or_create(user=request.user)

    unpaid_fine = sum(r.fine_amount for r in BorrowRecord.objects.filter(member=member, fine_paid=False))
    if unpaid_fine > 0:
        messages.warning(request, f"You have a pending fine of ₹{unpaid_fine}. Please clear it before borrowing new books.")
        return redirect('books:my_books')

    existing = BorrowRecord.objects.filter(member=member, book=book, status='borrowed').exists()
    if existing:
        messages.warning(request, "You have already borrowed this book.")
        return redirect('books:book_detail', book_id=book.id)

    BorrowRecord.objects.create(
        member=member,
        book=book,
        due_date=date.today() + timedelta(days=14),
        status='borrowed',
    )
    book.available_copies -= 1
    book.save()

    Reservation.objects.filter(member=member, book=book, status='ready').update(status='fulfilled')

    messages.success(request, f"'{book.title}' successfully borrowed! Due in 14 days.")
    return redirect('books:book_detail', book_id=book.id)


@login_required
def reserve_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    member, created = Member.objects.get_or_create(user=request.user)

    if book.is_available:
        messages.info(request, "This book is available. You can borrow it directly.")
        return redirect('books:book_detail', book_id=book.id)

    existing = Reservation.objects.filter(member=member, book=book, status__in=['waiting', 'ready']).first()
    if existing:
        messages.warning(request, f"You are already in the waitlist at position #{existing.position}.")
        return redirect('books:book_detail', book_id=book.id)

    reservation = Reservation.objects.create(member=member, book=book, status='waiting')
    messages.success(request, f"'{book.title}' waitlist joined! Your position: #{reservation.position}")
    return redirect('books:book_detail', book_id=book.id)


@login_required
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, member__user=request.user)

    if reservation.status not in ['waiting', 'ready']:
        messages.warning(request, "This reservation cannot be cancelled.")
        return redirect('books:my_reservations')

    book_title = reservation.book.title
    reservation.status = 'cancelled'
    reservation.save()

    messages.success(request, f"Reservation for '{book_title}' cancelled.")
    return redirect('books:my_reservations')


@login_required
def my_reservations(request):
    member, created = Member.objects.get_or_create(user=request.user)
    reservations = Reservation.objects.filter(member=member).exclude(status='cancelled').order_by('-reserved_on')

    return render(request, 'books/my_reservations.html', {
        'reservations': reservations,
    })


@login_required
def add_review(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    member, created = Member.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')

        Review.objects.update_or_create(
            book=book, member=member,
            defaults={'rating': rating, 'comment': comment}
        )
        messages.success(request, "Review submitted successfully!")
        return redirect('books:book_detail', book_id=book.id)

    return render(request, 'books/add_review.html', {'book': book})


def recommendations(request):
    recommendations_list = []

    if request.user.is_authenticated:
        try:
            member = Member.objects.get(user=request.user)

            borrowed_books = list(
                BorrowRecord.objects.filter(member=member).values_list('book', flat=True)
            )
            borrowed_categories = list(
                Book.objects.filter(id__in=borrowed_books).values_list('category', flat=True)
            )

            category_recs = Book.objects.filter(
                category__in=borrowed_categories
            ).exclude(id__in=borrowed_books).distinct()[:4]

            for book in category_recs:
                reason = f"Based on your interest in {book.category.name}" if book.category else "Based on your reading history"
                recommendations_list.append({
                    'book': book,
                    'reason': reason,
                    'type': 'Category'
                })

            similar_members = list(
                Member.objects.filter(
                    borrow_records__book__in=borrowed_books
                ).exclude(id=member.id).distinct().values_list('id', flat=True)
            )

            similar_books = list(
                BorrowRecord.objects.filter(
                    member__in=similar_members
                ).exclude(book__in=borrowed_books).values_list('book', flat=True).distinct()
            )

            for book in Book.objects.filter(id__in=similar_books[:4]):
                recommendations_list.append({
                    'book': book,
                    'reason': "Users like you also read this",
                    'type': 'Similar Users'
                })

            top_rated = Book.objects.exclude(
                id__in=borrowed_books
            ).annotate(
                avg_rating=Avg('reviews__rating')
            ).filter(avg_rating__gte=4).order_by('-avg_rating')[:4]

            for book in top_rated:
                recommendations_list.append({
                    'book': book,
                    'reason': f"Top rated ({book.average_rating}★) - You haven't read it yet",
                    'type': 'Top Rated'
                })

        except Member.DoesNotExist:
            pass

    if not recommendations_list:
        top_books = Book.objects.all()[:6]
        for book in top_books:
            recommendations_list.append({
                'book': book,
                'reason': "Popular in library",
                'type': 'Popular'
            })

    return render(request, 'books/recommendations.html', {'recommendations': recommendations_list})


@login_required
def my_books(request):
    member, created = Member.objects.get_or_create(user=request.user)
    borrow_records = BorrowRecord.objects.filter(member=member).order_by('-borrow_date')

    today = date.today()
    for record in borrow_records:
        if record.status == 'borrowed' and record.due_date < today:
            record.status = 'overdue'
            record.save()

    total_unpaid_fine = sum(r.fine_amount for r in borrow_records if not r.fine_paid)

    return render(request, 'books/my_books.html', {
        'borrow_records': borrow_records,
        'total_unpaid_fine': total_unpaid_fine,
    })


@login_required
def return_book(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id, member__user=request.user)

    if record.status == 'returned':
        messages.warning(request, "This book has already been returned.")
        return redirect('books:my_books')

    fine = record.fine_amount
    book = record.book

    record.status = 'returned'
    record.return_date = date.today()
    record.save()

    book.available_copies += 1
    book.save()

    next_reservation = Reservation.objects.filter(book=book, status='waiting').order_by('reserved_on').first()
    if next_reservation:
        next_reservation.status = 'ready'
        next_reservation.notified = True
        next_reservation.save()
        send_waitlist_ready(next_reservation)

    if fine > 0:
        messages.warning(request, f"'{book.title}' returned. Late return fine of ₹{fine}. Please clear it.")
    else:
        messages.success(request, f"'{book.title}' returned successfully! No fine.")

    return redirect('books:my_books')


@login_required
def pay_fine(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id, member__user=request.user)

    if record.fine_paid:
        messages.info(request, "This fine has already been paid.")
        return redirect('books:my_books')

    if record.fine_amount <= 0:
        messages.info(request, "No fine on this record.")
        return redirect('books:my_books')

    record.fine_paid = True
    record.save()

    messages.success(request, f"₹{record.fine_amount} fine paid successfully!")
    return redirect('books:my_books')


@login_required
def renew_book(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id, member__user=request.user)

    if record.status == 'returned':
        messages.error(request, "This book has already been returned.")
        return redirect('books:my_books')

    if record.renewal_count >= 2:
        messages.error(request, "Maximum renewals reached (2). Please return the book.")
        return redirect('books:my_books')

    if date.today() > record.due_date:
        messages.error(request, "Cannot renew overdue book. Please return it first.")
        return redirect('books:my_books')

    record.due_date = record.due_date + timedelta(days=14)
    record.renewal_count += 1
    record.save()

    messages.success(request, f"'{record.book.title}' renewed! New due date: {record.due_date} (Renewal {record.renewal_count}/2)")
    return redirect('books:my_books')

@login_required
def profile(request):
    member, created = Member.objects.get_or_create(user=request.user)

    total_borrowed = BorrowRecord.objects.filter(member=member).count()
    currently_borrowed = BorrowRecord.objects.filter(member=member, status='borrowed').count()
    returned = BorrowRecord.objects.filter(member=member, status='returned').count()
    overdue = BorrowRecord.objects.filter(member=member, status='overdue').count()
    reviews_count = Review.objects.filter(member=member).count()
    total_fine = sum(r.fine_amount for r in BorrowRecord.objects.filter(member=member, fine_paid=False))
    reservations_count = Reservation.objects.filter(member=member, status__in=['waiting', 'ready']).count()

    return render(request, 'books/profile.html', {
        'member': member,
        'total_borrowed': total_borrowed,
        'currently_borrowed': currently_borrowed,
        'returned': returned,
        'overdue': overdue,
        'reviews_count': reviews_count,
        'total_fine': total_fine,
        'reservations_count': reservations_count,
    })


@login_required
@login_required
def edit_profile(request):
    member, created = Member.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        request.user.email = request.POST.get('email', '')
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.save()

        member.phone = request.POST.get('phone', '')
        member.address = request.POST.get('address', '')

        # Profile photo upload
        if 'profile_photo' in request.FILES:
            member.profile_photo = request.FILES['profile_photo']

        member.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('books:profile')

    return render(request, 'books/edit_profile.html', {'member': member})

# ============ CHATBOT VIEWS ============

def chatbot_page(request):
    return render(request, 'books/chatbot.html')


@csrf_exempt
def chatbot_api(request):
    if request.method == 'POST':
        # Data handle karein
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                message = data.get('message', '').strip()
            except json.JSONDecodeError:
                message = ''
        else:
            message = request.POST.get('message', '').strip()

        if not message:
            return JsonResponse({'error': 'Empty message'}, status=400)

        try:
            user = request.user if request.user.is_authenticated else None
            result = chatbot_response(message, user)

            # SAFE CHECK: Agar result None hai toh default dictionary banao
            if not isinstance(result, dict):
                result = {
                    'text': "I am having trouble understanding right now. Please try asking something else.",
                    'books': []
                }

            books_data = []
            for book in result.get('books', []):
                books_data.append({
                    'id': book.id,
                    'title': book.title,
                    'author': book.author,
                    'available': book.is_available,
                    'available_copies': book.available_copies,
                    'average_rating': book.average_rating,
                    'category': book.category.name if book.category else 'Uncategorized',
                })

            return JsonResponse({
                'text': result.get('text', ''),
                'books': books_data,
            })
        except Exception as e:
            print(f"CHATBOT ERROR: {str(e)}")
            return JsonResponse({'text': f"Error: {str(e)}", 'books': []}, status=500)

    return JsonResponse({'error': 'POST required'}, status=405)

# ============ LIBRARIAN ISSUE SYSTEM ============

@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def librarian_issue(request):
    if request.method == 'POST':
        card_number = request.POST.get('card_number', '').strip()
        isbn = request.POST.get('isbn', '').strip()

        try:
            member = Member.objects.get(library_card_number=card_number)
        except Member.DoesNotExist:
            messages.error(request, f"Member not found with card number: {card_number}")
            return redirect('books:librarian_issue')

        try:
            book = Book.objects.get(isbn=isbn)
        except Book.DoesNotExist:
            messages.error(request, f"Book not found with ISBN: {isbn}")
            return redirect('books:librarian_issue')

        if not book.is_available:
            messages.error(request, f"'{book.title}' is not available.")
            return redirect('books:librarian_issue')

        unpaid_fine = sum(r.fine_amount for r in BorrowRecord.objects.filter(member=member, fine_paid=False))
        if unpaid_fine > 0:
            messages.error(request, f"{member.user.username} has pending fine of ₹{unpaid_fine}.")
            return redirect('books:librarian_issue')

        existing = BorrowRecord.objects.filter(member=member, book=book, status='borrowed').exists()
        if existing:
            messages.error(request, f"{member.user.username} has already borrowed this book.")
            return redirect('books:librarian_issue')

        record = BorrowRecord.objects.create(
            member=member,
            book=book,
            due_date=date.today() + timedelta(days=14),
            status='borrowed',
        )
        book.available_copies -= 1
        book.save()

        messages.success(request, f"'{book.title}' issued to {member.user.username} (Card: {member.library_card_number}). Due: {record.due_date}")
        return redirect('books:issue_receipt', record_id=record.id)

    total_members = Member.objects.count()
    total_books = Book.objects.count()
    recent_records = BorrowRecord.objects.select_related('member__user', 'book').order_by('-borrow_date')[:5]

    return render(request, 'books/librarian_issue.html', {
        'total_members': total_members,
        'total_books': total_books,
        'recent_records': recent_records,
    })


@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def issue_receipt(request, record_id):
    record = get_object_or_404(BorrowRecord, id=record_id)
    return render(request, 'books/receipt.html', {'record': record})


# ============ EMAIL NOTIFICATION ADMIN VIEW ============

@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def send_all_reminders(request):
    today = date.today()
    due_soon = 0
    overdue_count = 0
    fine_count = 0

    due_records = BorrowRecord.objects.filter(status='borrowed', due_date=today + timedelta(days=2))
    for record in due_records:
        send_due_reminder(record)
        due_soon += 1

    overdue_records = BorrowRecord.objects.filter(status='borrowed', due_date__lt=today)
    for record in overdue_records:
        send_overdue_notice(record)
        overdue_count += 1

    fine_records = BorrowRecord.objects.filter(fine_paid=False, return_date__isnull=False)
    for record in fine_records:
        if record.fine_amount > 0:
            send_fine_reminder(record)
            fine_count += 1

    messages.success(request, f"Emails sent: {due_soon} due reminders, {overdue_count} overdue notices, {fine_count} fine reminders.")
    return redirect('books:reports')


# ============ SCANNER VIEW ============

@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def scanner_view(request):
    return render(request, 'books/scanner.html')


# ============ CSV EXPORT FUNCTIONS ============

def is_admin(user):
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin)
def export_books_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="books_report.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Title', 'Author', 'ISBN', 'Category', 'Total Copies', 'Available Copies', 'Published Year', 'Avg Rating', 'Waitlist'])
    for book in Book.objects.all():
        writer.writerow([
            book.title, book.author, book.isbn,
            book.category.name if book.category else 'Uncategorized',
            book.total_copies, book.available_copies,
            book.published_year or '', book.average_rating,
            book.waitlist_count,
        ])
    return response


@user_passes_test(is_admin)
def export_borrow_records_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="borrow_records.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Member', 'Card No', 'Book', 'Borrow Date', 'Due Date', 'Return Date', 'Status', 'Days Overdue', 'Fine (₹)', 'Fine Paid'])
    for record in BorrowRecord.objects.all().order_by('-borrow_date'):
        writer.writerow([
            record.member.user.username, record.member.library_card_number or '',
            record.book.title,
            record.borrow_date, record.due_date,
            record.return_date or '', record.status,
            record.days_overdue, record.fine_amount,
            'Yes' if record.fine_paid else 'No',
        ])
    return response


@user_passes_test(is_admin)
def export_members_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="members.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Username', 'Card No', 'Email', 'Phone', 'Address', 'Membership Date', 'Active', 'Total Borrowed', 'Pending Fine (₹)'])
    for member in Member.objects.all():
        total = BorrowRecord.objects.filter(member=member).count()
        pending_fine = sum(r.fine_amount for r in BorrowRecord.objects.filter(member=member, fine_paid=False))
        writer.writerow([
            member.user.username, member.library_card_number or '',
            member.user.email,
            member.phone or '', member.address or '',
            member.membership_date,
            'Yes' if member.is_active else 'No',
            total, pending_fine,
        ])
    return response


@user_passes_test(is_admin)
def export_reservations_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reservations.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Member', 'Card No', 'Book', 'Reserved On', 'Status', 'Position'])
    for res in Reservation.objects.all().order_by('-reserved_on'):
        writer.writerow([
            res.member.user.username, res.member.library_card_number or '',
            res.book.title,
            res.reserved_on.strftime('%Y-%m-%d %H:%M'),
            res.status, res.position or '-',
        ])
    return response


@user_passes_test(is_admin)
def reports_dashboard(request):
    total_books = Book.objects.count()
    total_members = Member.objects.count()
    total_borrowed = BorrowRecord.objects.filter(status='borrowed').count()
    total_overdue = BorrowRecord.objects.filter(status='overdue').count()
    total_returned = BorrowRecord.objects.filter(status='returned').count()
    total_reviews = Review.objects.count()
    total_fine_collected = sum(r.fine_amount for r in BorrowRecord.objects.filter(fine_paid=True))
    total_fine_pending = sum(r.fine_amount for r in BorrowRecord.objects.filter(fine_paid=False))
    total_waitlist = Reservation.objects.filter(status='waiting').count()
    total_ready = Reservation.objects.filter(status='ready').count()

    return render(request, 'books/reports.html', {
        'total_books': total_books,
        'total_members': total_members,
        'total_borrowed': total_borrowed,
        'total_overdue': total_overdue,
        'total_returned': total_returned,
        'total_reviews': total_reviews,
        'total_fine_collected': total_fine_collected,
        'total_fine_pending': total_fine_pending,
        'total_waitlist': total_waitlist,
        'total_ready': total_ready,
    })


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('books:register')

        user = User.objects.create_user(username=username, email=email, password=password)
        Member.objects.create(user=user)
        login(request, user)
        messages.success(request, "Registration successful!")
        return redirect('books:home')

    return render(request, 'books/register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return redirect('books:home')
        else:
            messages.error(request, "Invalid credentials.")
    return render(request, 'books/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('books:home')

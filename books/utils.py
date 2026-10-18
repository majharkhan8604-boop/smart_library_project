import urllib.request
import urllib.parse
import json
from django.core.mail import send_mail
from django.conf import settings
from datetime import date
from django.db.models import Q, Avg


def fetch_cover_from_google_books(isbn):
    API_KEY = 'AIzaSyCKvoI9D7usNqzWqKKLEO8WJpOW4K2DwRI'

    queries = [isbn, f"isbn:{isbn}", isbn.replace('-', '')]

    for query in queries:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}&key={API_KEY}"
            req = urllib.request.Request(url, headers={'User-Agent': 'SmartLibrary/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get('totalItems', 0) > 0:
                for item in data['items']:
                    volume_info = item.get('volumeInfo', {})
                    image_links = volume_info.get('imageLinks', {})
                    for size in ['extraLarge', 'large', 'medium', 'small', 'thumbnail', 'smallThumbnail']:
                        if size in image_links:
                            return image_links[size].replace('http://', 'https://')
        except Exception as e:
            print(f"Query '{query}' failed: {e}")

    return None


def fetch_cover_from_openlibrary(isbn):
    try:
        url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        req = urllib.request.Request(url, headers={'User-Agent': 'SmartLibrary/1.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'image' in content_type:
                    return url
        return None
    except Exception as e:
        print(f"Open Library failed for ISBN {isbn}: {e}")
        return None


# ============ EMAIL FUNCTIONS ============

def send_due_reminder(borrow_record):
    days_left = (borrow_record.due_date - date.today()).days
    subject = f'Reminder: "{borrow_record.book.title}" due in {days_left} days'
    message = f"Hello {borrow_record.member.user.username},\n\nYour book is due on {borrow_record.due_date}."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


def send_overdue_notice(borrow_record):
    subject = f'OVERDUE: "{borrow_record.book.title}"'
    message = f"Hello {borrow_record.member.user.username},\n\nYour book is overdue."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


def send_waitlist_ready(reservation):
    subject = f'Ready: "{reservation.book.title}"'
    message = f"Hello {reservation.member.user.username},\n\nYour reserved book is ready."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.member.user.email], fail_silently=True)


def send_fine_reminder(borrow_record):
    subject = f'Fine: Rs. {borrow_record.fine_amount}'
    message = f"Hello {borrow_record.member.user.username},\n\nYou have a pending fine."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


# ============ CHATBOT LOGIC ============

def chatbot_response(message, user=None):
    from .models import Book, Category, BorrowRecord, Member
    message_lower = message.lower().strip()
    response = {'text': '', 'books': []}

    greetings = ['hi', 'hello', 'hey', 'namaste']
    if any(g in message_lower.split() for g in greetings) or message_lower in greetings:
        response['text'] = "Hello! I'm the assistant. Ask me for books!"
        return response

    if 'help' in message_lower:
        response['text'] = "Try: 'suggest science books', 'best rated books', 'available books'"
        return response

    categories = Category.objects.all()
    matched_category = None
    for cat in categories:
        if cat.name.lower() in message_lower:
            matched_category = cat
            break

    if matched_category:
        books = Book.objects.filter(category=matched_category)[:6]
        if books:
            response['text'] = f"Here are {matched_category.name} books:"
            response['books'] = list(books)
            return response

    if 'best' in message_lower or 'top' in message_lower:
        books = Book.objects.annotate(avg_rating=Avg('reviews__rating')).filter(avg_rating__gte=4).order_by('-avg_rating')[:5]
        response['text'] = "Top rated books:"
        response['books'] = list(books)
        return response

    if 'available' in message_lower:
        books = Book.objects.filter(available_copies__gt=0)[:6]
        response['text'] = "Available books:"
        response['books'] = list(books)
        return response

    words = [w for w in message_lower.split() if len(w) > 2]
    query = Q()
    for word in words:
        query |= Q(title__icontains=word) | Q(author__icontains=word)
    
    if words:
        books = Book.objects.filter(query).distinct()[:6]
        if books:
            response['text'] = "I found these books:"
            response['books'] = list(books)
            return response

    response['text'] = "Sorry, I didn't understand. Type 'help' for options."
    return response

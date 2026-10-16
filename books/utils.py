import urllib.request
import urllib.parse
import json
from django.core.mail import send_mail
from django.conf import settings
from datetime import date
from django.db.models import Q, Avg


# ============ GOOGLE BOOKS API ============

def fetch_cover_from_google_books(isbn):
    """
    Fetch cover image URL from Google Books API using ISBN.
    Returns: URL string or None
    """
    try:
        query = f"isbn:{isbn}"
        url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}"

        req = urllib.request.Request(url, headers={'User-Agent': 'SmartLibrary/1.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))

        if data.get('totalItems', 0) > 0:
            volume_info = data['items'][0].get('volumeInfo', {})
            image_links = volume_info.get('imageLinks', {})

            for size in ['extraLarge', 'large', 'medium', 'small', 'thumbnail', 'smallThumbnail']:
                if size in image_links:
                    img_url = image_links[size].replace('http://', 'https://')
                    return img_url

        return None
    except Exception as e:
        print(f"Cover fetch failed for ISBN {isbn}: {e}")
        return None


# ============ EMAIL FUNCTIONS ============

def send_due_reminder(borrow_record):
    days_left = (borrow_record.due_date - date.today()).days
    subject = f'Reminder: "{borrow_record.book.title}" due in {days_left} days'
    message = f"""
Hello {borrow_record.member.user.username},

This is a friendly reminder that the book "{borrow_record.book.title}" by {borrow_record.book.author} is due on {borrow_record.due_date}.

Days remaining: {days_left}

Please return it on time to avoid a fine of Rs. 5/day.

Happy Reading!
Smart Library Team
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


def send_overdue_notice(borrow_record):
    days_overdue = borrow_record.days_overdue
    fine = borrow_record.fine_amount
    subject = f'OVERDUE: "{borrow_record.book.title}" is {days_overdue} days late'
    message = f"""
Hello {borrow_record.member.user.username},

The book "{borrow_record.book.title}" was due on {borrow_record.due_date} and is now {days_overdue} days overdue.

Current fine: Rs. {fine}

Please return the book as soon as possible. Fine increases by Rs. 5 each day.

Smart Library Team
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


def send_waitlist_ready(reservation):
    subject = f'Good News: "{reservation.book.title}" is ready for pickup!'
    message = f"""
Hello {reservation.member.user.username},

Great news! The book "{reservation.book.title}" by {reservation.book.author} that you reserved is now available.

Please visit the library within 3 days to borrow it, otherwise it will be passed to the next person in queue.

Smart Library Team
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reservation.member.user.email], fail_silently=True)


def send_fine_reminder(borrow_record):
    subject = f'Pending Fine: Rs. {borrow_record.fine_amount} for "{borrow_record.book.title}"'
    message = f"""
Hello {borrow_record.member.user.username},

You have a pending fine of Rs. {borrow_record.fine_amount} for the book "{borrow_record.book.title}".

Please clear it to continue borrowing new books.

Smart Library Team
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [borrow_record.member.user.email], fail_silently=True)


# ============ CHATBOT LOGIC ============

def chatbot_response(message, user=None):
    from .models import Book, Category, BorrowRecord, Member

    message_lower = message.lower().strip()
    response = {'text': '', 'books': []}

    greetings = ['hi', 'hello', 'hey', 'namaste', 'hii', 'helo']
    if any(g in message_lower.split() for g in greetings) or message_lower in greetings:
        response['text'] = "Hello! 👋 I'm the Smart Library assistant. You can ask me about books. For example:\n\n• 'suggest science fiction books'\n• 'best rated books'\n• 'programming books'\n• 'books by Paulo Coelho'"
        return response

    if 'help' in message_lower:
        response['text'] = "I can help you with:\n\n• Category search: 'science books', 'history books'\n• Author search: 'books by Stephen Hawking'\n• Ratings: 'best books', 'top rated'\n• Availability: 'available books'\n• Recommendations: 'recommend books'"
        return response

    if 'thank' in message_lower or 'thanks' in message_lower:
        response['text'] = "You're welcome! 😊 Let me know if you need more book suggestions."
        return response

    if 'by ' in message_lower or 'author' in message_lower:
        query = message_lower.replace('books by', '').replace('author', '').replace('by', '').strip()
        if query:
            books = Book.objects.filter(author__icontains=query)[:5]
            if books:
                response['text'] = f"I found {books.count()} books by '{query}':"
                response['books'] = list(books)
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
            response['text'] = f"I found {books.count()} books in the {matched_category.name} category:"
            response['books'] = list(books)
            return response

    if 'best' in message_lower or 'top' in message_lower or 'highest' in message_lower or 'rating' in message_lower:
        books = Book.objects.annotate(avg_rating=Avg('reviews__rating')).filter(avg_rating__gte=4).order_by('-avg_rating')[:5]
        if books:
            response['text'] = "Here are the top rated books (4★+):"
            response['books'] = list(books)
            return response
        else:
            response['text'] = "No books have received a 4★+ rating yet."
            return response

    if 'available' in message_lower:
        books = Book.objects.filter(available_copies__gt=0)[:6]
        response['text'] = "These books are currently available:"
        response['books'] = list(books)
        return response

    if 'recommend' in message_lower or 'suggest' in message_lower:
        if user and user.is_authenticated:
            try:
                member = Member.objects.get(user=user)
                borrowed = list(BorrowRecord.objects.filter(member=member).values_list('book', flat=True))
                borrowed_cats = list(Book.objects.filter(id__in=borrowed).values_list('category', flat=True))

                if borrowed_cats:
                    books = Book.objects.filter(category__in=borrowed_cats).exclude(id__in=borrowed).distinct()[:5]
                    response['text'] = "Based on your reading history, here are my recommendations:"
                    response['books'] = list(books)
                    return response
            except Member.DoesNotExist:
                pass

        books = Book.objects.all()[:5]
        response['text'] = "Here are some popular books you might enjoy:"
        response['books'] = list(books)
        return response

    words = [w for w in message_lower.split() if len(w) > 2]
    query = Q()
    for word in words:
        query |= Q(title__icontains=word) | Q(author__icontains=word) | Q(description__icontains=word)

    if words:
        books = Book.objects.filter(query).distinct()[:6]
        if books:
            response['text'] = f"I found {books.count()} books related to your query:"
            response['books'] = list(books)
            return response

    response['text'] = "Sorry, I didn't understand that. 🤔 Try asking like:\n\n• 'suggest science books'\n• 'best rated books'\n• 'books by author name'\n• 'available books'\n\nOr type 'help'."
    return response

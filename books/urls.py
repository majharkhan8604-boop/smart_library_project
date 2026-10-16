from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('renew/<int:record_id>/', views.renew_book, name='renew_book'),
    path('librarian/issue/', views.librarian_issue, name='librarian_issue'),
    path('librarian/receipt/<int:record_id>/', views.issue_receipt, name='issue_receipt'),
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('api/autocomplete/', views.autocomplete_books, name='autocomplete_books'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('books/<int:book_id>/borrow/', views.borrow_book, name='borrow_book'),
    path('books/<int:book_id>/reserve/', views.reserve_book, name='reserve_book'),
    path('books/<int:book_id>/review/', views.add_review, name='add_review'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('my-books/', views.my_books, name='my_books'),
    path('my-reservations/', views.my_reservations, name='my_reservations'),
    path('cancel-reservation/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('return/<int:record_id>/', views.return_book, name='return_book'),
    path('pay-fine/<int:record_id>/', views.pay_fine, name='pay_fine'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/send-reminders/', views.send_all_reminders, name='send_reminders'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('chatbot/', views.chatbot_page, name='chatbot'),
    path('chatbot/api/', views.chatbot_api, name='chatbot_api'),
    path('reports/export/books/', views.export_books_csv, name='export_books'),
    path('reports/export/borrow-records/', views.export_borrow_records_csv, name='export_borrow_records'),
    path('reports/export/members/', views.export_members_csv, name='export_members'),
    path('reports/export/reservations/', views.export_reservations_csv, name='export_reservations'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'categories', api_views.CategoryViewSet, basename='category')
router.register(r'books', api_views.BookViewSet, basename='book')
router.register(r'members', api_views.MemberViewSet, basename='member')
router.register(r'borrow-records', api_views.BorrowRecordViewSet, basename='borrow-record')
router.register(r'reviews', api_views.ReviewViewSet, basename='review')
router.register(r'reservations', api_views.ReservationViewSet, basename='reservation')

app_name = 'api'

urlpatterns = [
    path('auth/register/', api_views.api_register, name='register'),
    path('auth/login/', api_views.api_login, name='login'),
    path('auth/logout/', api_views.api_logout, name='logout'),
    path('auth/profile/', api_views.api_profile, name='profile'),
    path('books/<int:book_id>/borrow/', api_views.api_borrow_book, name='borrow'),
    path('borrow-records/<int:record_id>/return/', api_views.api_return_book, name='return'),
    path('', include(router.urls)),
]

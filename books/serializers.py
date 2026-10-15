from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Book, Member, BorrowRecord, Review, Reservation


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class CategorySerializer(serializers.ModelSerializer):
    book_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'book_count']

    def get_book_count(self, obj):
        return obj.books.count()


class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    waitlist_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'isbn', 'category', 'category_name',
            'description', 'cover_image', 'total_copies', 'available_copies',
            'published_year', 'added_on', 'average_rating', 'is_available',
            'waitlist_count'
        ]


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    total_fine = serializers.FloatField(read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'user', 'username', 'email', 'phone', 'address', 'membership_date', 'is_active', 'total_fine']
        read_only_fields = ['user', 'membership_date']


class BorrowRecordSerializer(serializers.ModelSerializer):
    member_username = serializers.CharField(source='member.user.username', read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    fine_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = BorrowRecord
        fields = [
            'id', 'member', 'member_username', 'book', 'book_title',
            'borrow_date', 'due_date', 'return_date', 'status',
            'fine_paid', 'days_overdue', 'fine_amount'
        ]


class ReviewSerializer(serializers.ModelSerializer):
    member_username = serializers.CharField(source='member.user.username', read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'book', 'book_title', 'member', 'member_username', 'rating', 'comment', 'created_on']


class ReservationSerializer(serializers.ModelSerializer):
    member_username = serializers.CharField(source='member.user.username', read_only=True)
    book_title = serializers.CharField(source='book.title', read_only=True)
    position = serializers.IntegerField(read_only=True)

    class Meta:
        model = Reservation
        fields = ['id', 'member', 'member_username', 'book', 'book_title', 'reserved_on', 'status', 'notified', 'position']

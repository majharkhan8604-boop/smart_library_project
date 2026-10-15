from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q, Avg
from datetime import date, timedelta

from .models import Category, Book, Member, BorrowRecord, Review, Reservation
from .serializers import (
    CategorySerializer, BookSerializer, MemberSerializer,
    BorrowRecordSerializer, ReviewSerializer, ReservationSerializer,
    UserSerializer
)


# ============ AUTH ENDPOINTS ============

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password:
        return Response({'error': 'Username and password required'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    Member.objects.create(user=user)
    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({'message': 'Logged out successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_profile(request):
    try:
        member = Member.objects.get(user=request.user)
        return Response(MemberSerializer(member).data)
    except Member.DoesNotExist:
        return Response({'error': 'Member profile not found'}, status=404)


# ============ VIEWSETS ============

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'author', 'isbn', 'description']
    ordering_fields = ['title', 'author', 'published_year', 'added_on']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def available(self, request):
        books = Book.objects.filter(available_copies__gt=0)
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        books = Book.objects.annotate(
            avg_rating=Avg('reviews__rating')
        ).filter(avg_rating__gte=4).order_by('-avg_rating')[:10]
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)


class MemberViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__username', 'phone']


class BorrowRecordViewSet(viewsets.ModelViewSet):
    queryset = BorrowRecord.objects.all()
    serializer_class = BorrowRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['borrow_date', 'due_date']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return BorrowRecord.objects.all()
        try:
            member = Member.objects.get(user=user)
            return BorrowRecord.objects.filter(member=member)
        except Member.DoesNotExist:
            return BorrowRecord.objects.none()

    @action(detail=False, methods=['get'])
    def my_records(self, request):
        try:
            member = Member.objects.get(user=request.user)
            records = BorrowRecord.objects.filter(member=member)
            serializer = self.get_serializer(records, many=True)
            return Response(serializer.data)
        except Member.DoesNotExist:
            return Response({'error': 'Member profile not found'}, status=404)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        today = date.today()
        records = BorrowRecord.objects.filter(status='borrowed', due_date__lt=today)
        if not request.user.is_staff:
            try:
                member = Member.objects.get(user=request.user)
                records = records.filter(member=member)
            except Member.DoesNotExist:
                return Response([])
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.all()

    def perform_create(self, serializer):
        try:
            member = Member.objects.get(user=self.request.user)
            serializer.save(member=member)
        except Member.DoesNotExist:
            raise Exception("Member profile required")


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Reservation.objects.all()
        try:
            member = Member.objects.get(user=user)
            return Reservation.objects.filter(member=member)
        except Member.DoesNotExist:
            return Reservation.objects.none()

    def perform_create(self, serializer):
        try:
            member = Member.objects.get(user=self.request.user)
            serializer.save(member=member, status='waiting')
        except Member.DoesNotExist:
            raise Exception("Member profile required")

    @action(detail=False, methods=['get'])
    def my_reservations(self, request):
        try:
            member = Member.objects.get(user=request.user)
            reservations = Reservation.objects.filter(member=member).exclude(status='cancelled')
            serializer = self.get_serializer(reservations, many=True)
            return Response(serializer.data)
        except Member.DoesNotExist:
            return Response([])


# ============ BORROW/RETURN ACTIONS ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_borrow_book(request, book_id):
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return Response({'error': 'Book not found'}, status=404)

    if not book.is_available:
        return Response({'error': 'Book not available'}, status=400)

    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        return Response({'error': 'Member profile not found'}, status=404)

    existing = BorrowRecord.objects.filter(member=member, book=book, status='borrowed').exists()
    if existing:
        return Response({'error': 'Already borrowed'}, status=400)

    record = BorrowRecord.objects.create(
        member=member,
        book=book,
        due_date=date.today() + timedelta(days=14),
        status='borrowed',
    )
    book.available_copies -= 1
    book.save()

    return Response(BorrowRecordSerializer(record).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_return_book(request, record_id):
    try:
        member = Member.objects.get(user=request.user)
        record = BorrowRecord.objects.get(id=record_id, member=member)
    except (Member.DoesNotExist, BorrowRecord.DoesNotExist):
        return Response({'error': 'Record not found'}, status=404)

    if record.status == 'returned':
        return Response({'error': 'Already returned'}, status=400)

    record.status = 'returned'
    record.return_date = date.today()
    record.save()

    book = record.book
    book.available_copies += 1
    book.save()

    return Response(BorrowRecordSerializer(record).data)

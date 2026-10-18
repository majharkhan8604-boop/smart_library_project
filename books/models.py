from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150)
    isbn = models.CharField(max_length=13, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='books')
    description = models.TextField(blank=True)
    cover_image = models.CharField(max_length=500, blank=True, null=True)
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)
    published_year = models.PositiveIntegerField(blank=True, null=True)
    added_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} by {self.author}"

    @property
    def is_available(self):
        return self.available_copies > 0

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum(r.rating for r in reviews) / reviews.count(), 1)
        return 0

    @property
    def waitlist_count(self):
        return self.reservations.filter(status='waiting').count()
class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='member')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    membership_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    library_card_number = models.CharField(max_length=20, unique=True, blank=True)
    
    # Naya field Email Verification ke liye
    email_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.library_card_number:
            last_member = Member.objects.order_by('-id').first()
            num = (last_member.id + 1) if last_member else 1
            # Ensure uniqueness — agar number already exists, increment karein
            while Member.objects.filter(library_card_number=f"LIB2026{num:04d}").exists():
                num += 1
            self.library_card_number = f"LIB2026{num:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} ({self.library_card_number})"

    @property
    def total_fine(self):
        return sum(record.fine_amount for record in self.borrow_records.all())
class BorrowRecord(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]

    FINE_PER_DAY = 5

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='borrow_records')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrow_records')
    borrow_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    return_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='borrowed')
    fine_paid = models.BooleanField(default=False)
    renewal_count = models.PositiveIntegerField(default=0)
    def __str__(self):
        return f"{self.member.user.username} - {self.book.title}"

    @property
    def days_overdue(self):
        if self.status == 'returned' and self.return_date:
            if self.return_date > self.due_date:
                return (self.return_date - self.due_date).days
            return 0
        elif self.status in ['borrowed', 'overdue']:
            today = date.today()
            if today > self.due_date:
                return (today - self.due_date).days
        return 0
    @property
    def can_renew(self):
        """Check if book can be renewed"""
        if self.status != 'borrowed':
            return False
        if self.renewal_count >= 2:
            return False
        if date.today() > self.due_date:
            return False
        return True
    @property
    def fine_amount(self):
        return self.days_overdue * self.FINE_PER_DAY


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('ready', 'Ready for Pickup'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='reservations')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reservations')
    reserved_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='waiting')
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ['reserved_on']
        unique_together = ('member', 'book', 'status')

    def __str__(self):
        return f"{self.member.user.username} - {self.book.title} ({self.status})"

    @property
    def position(self):
        if self.status != 'waiting':
            return None
        waiting = Reservation.objects.filter(
            book=self.book, status='waiting', reserved_on__lt=self.reserved_on
        ).count()
        return waiting + 1


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('book', 'member')

    def __str__(self):
        return f"{self.book.title} - {self.rating}★"

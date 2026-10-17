# 📚 Smart Library Management System

> A modern, full-featured library management system with book recommendations, AI chatbot, and barcode scanning.

**Developed by [Mazhar Hussain](https://github.com/majharkhan8604-boop)**

---

## 🌐 Live Demo

🔗 **https://mazharhussain.pythonanywhere.com/**

---

## ✨ Features (36+)

### 📖 Core Features
- Book Management (CRUD)
- Category Management
- User Authentication (Login/Register)
- Member Profiles with Photos
- Borrow/Return System
- My Books Dashboard
- Review & Rating System
- Admin Panel

### 🚀 Advanced Features
- **Fine Calculation** (₹5/day)
- **Book Reservations** (Waitlist with position)
- **Auto-Notify Waitlist** (Email)
- **Search Autocomplete** (AJAX)
- **Email Notifications** (Due, Overdue, Fine)
- **Barcode Scanner** (ISBN via camera)
- **AI Chatbot** (Rule-based NLP)
- **REST API** (Django REST Framework)
- **CSV Reports** (4 types)
- **Reports Dashboard** (Statistics)
- **Pagination** (12 books/page)
- **Book Cover Auto-Fetch** (Google Books API)

### 🎯 Recommendation System
- **Category-based** (Based on reading history)
- **Collaborative Filtering** (Similar users)
- **Top Rated** (4★+ books)

### 📚 Library Management
- **Library Card Number** (Auto-generated)
- **Librarian Issue System** (Card + ISBN)
- **Barcode Scan Issue**
- **Issue Receipt** (Print/Download)
- **Renewal System** (Max 2, 14 days each)

### 🔒 Security
- **LoginRequiredMiddleware** (All pages protected)
- **Token Authentication** (API)
- **CSRF Protection**
- **SQL Injection Protection** (Django ORM)

### 🎨 Modern UI
- **Glassmorphism Design**
- **Gradient Themes**
- **Smooth Animations**
- **Profile Photo Upload**
- **Responsive (Mobile-friendly)**
- **Custom Scrollbar**
- **Google Fonts** (Inter + Poppins)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 4.2 |
| **Database** | MySQL (Local) / SQLite (Production) |
| **Frontend** | HTML5, CSS3, Bootstrap 5 |
| **API** | Django REST Framework |
| **JS** | Vanilla JS, AJAX, Fetch API |
| **Scanner** | html5-qrcode |
| **Email** | Django Console Backend |
| **Deployment** | PythonAnywhere |
| **Version Control** | Git + GitHub |

---

## 🚀 Local Setup

```bash
# Clone repository
git clone https://github.com/majharkhan8604-boop/smart_library_project.git
cd smart_library_project

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install django pymysql pillow djangorestframework

# Setup database (MySQL)
mysql -u root -p
CREATE DATABASE library_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'library_user'@'localhost' IDENTIFIED BY 'LibraryPass123!';
GRANT ALL PRIVILEGES ON library_db.* TO 'library_user'@'localhost';
FLUSH PRIVILEGES;
exit;

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver

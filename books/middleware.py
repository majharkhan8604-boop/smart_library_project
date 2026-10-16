import re
from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    """
    Middleware to require login for all pages except whitelisted URLs.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [re.compile(url) for url in getattr(settings, 'LOGIN_EXEMPT_URLS', [])]

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path_info.lstrip('/')
            if not any(pattern.match(path) for pattern in self.exempt_urls):
                login_url = settings.LOGIN_URL
                return redirect(f'{login_url}?next={request.path}')

        return self.get_response(request)

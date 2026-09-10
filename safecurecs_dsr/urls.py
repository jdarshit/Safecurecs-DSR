"""
URL configuration for safecurecs_dsr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import IndexRedirectView

admin.site.site_header = 'Safecurecs DSR Administration'
admin.site.site_title = 'Safecurecs DSR Administration'
admin.site.index_title = 'Administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', IndexRedirectView.as_view(), name='home'),
    path('', include('accounts.urls')),
    path('dsr/', include('dsr.urls')),
]

if settings.DEBUG:
    # Only profile_photos/ is directly served, even in dev - dsr_attachments/
    # contains private client data and must only ever be reached through the
    # authenticated dsr:attachment_download view (see CLAUDE.md). Serving just
    # this one subdirectory (rather than all of MEDIA_ROOT) makes that
    # protection real and testable locally, not just true in production.
    urlpatterns += static(
        settings.MEDIA_URL + 'profile_photos/',
        document_root=settings.MEDIA_ROOT / 'profile_photos',
    )

from django.urls import path

from . import views

app_name = 'dsr'

urlpatterns = [
    path('new/', views.DSRCreateView.as_view(), name='create'),
    path('my/', views.DSRListView.as_view(), name='my_reports'),
    path('all/', views.AdminDSRListView.as_view(), name='all_reports'),
    path('all/export/excel/', views.AdminDSRExcelExportView.as_view(), name='all_reports_export_excel'),
    path('all/export/pdf/', views.AdminDSRPDFExportView.as_view(), name='all_reports_export_pdf'),
    path('<int:pk>/', views.DSRDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DSRUpdateView.as_view(), name='edit'),
    path('<int:pk>/review/', views.AdminDSRReviewView.as_view(), name='review'),
    path('<int:pk>/export/pdf/', views.DSRSinglePDFExportView.as_view(), name='export_pdf'),
    path(
        '<int:pk>/attachments/<int:attachment_pk>/delete/',
        views.DSRAttachmentDeleteView.as_view(), name='attachment_delete',
    ),
    path('attachment/<int:pk>/download/', views.DSRAttachmentDownloadView.as_view(), name='attachment_download'),
]

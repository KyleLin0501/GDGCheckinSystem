# attendance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # 簽到主頁面 (GET 請求)
    path('', views.checkin_page, name='checkin_page'),

    # 處理簽到邏輯 (POST 請求，使用 AJAX)
    path('checkin/', views.handle_checkin, name='handle_checkin'),
    path('export/<int:course_id>/', views.export_checkins_csv, name='export_checkins_csv'),
    path('api/checkins/<int:course_id>/', views.get_checkin_list, name='get_checkin_list'),
]
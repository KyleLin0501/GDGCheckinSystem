from django.urls import path
from . import views

urlpatterns = [
    path('', views.checkin_page, name='checkin_page'),
    path('checkin/', views.handle_checkin, name='handle_checkin'),
    path('api/checkins/<str:course_id>/', views.get_checkin_list, name='get_checkin_list'),
    path('export/<str:course_id>/', views.export_checkins_csv, name='export_checkins_csv'),
    path('management/', views.management_page, name='management_page'),
    path('add_student/', views.add_student, name='add_student'),
    path('add_course/', views.add_course, name='add_course'),
    path('api/update_data/', views.update_data, name='update_data'),
    path('api/delete_data/', views.delete_data, name='delete_data'),
]

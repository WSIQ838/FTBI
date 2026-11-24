from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from academics import views
urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("courses/<int:pk>/", views.course, name="course"),
    path("assignments/<int:pk>/submit/", views.submit, name="submit"),
    path("submissions/<int:pk>/grade/", views.grade, name="grade"),
]

from academics import registrar_views as rv
urlpatterns += [path('record/',rv.student_record,name='student_record'),path('catalog/',rv.catalog,name='catalog'),path('register/<int:pk>/',rv.register,name='register'),path('admissions/',rv.admissions,name='admissions')]

from academics.service_views import student_services
urlpatterns += [path('services/',student_services,name='student_services')]

from academics import quiz_views
urlpatterns += [path('quizzes/',quiz_views.quizzes,name='quizzes'),path('quizzes/<int:pk>/',quiz_views.take_quiz,name='take_quiz')]

from academics import faculty
urlpatterns += [path('faculty/<int:pk>/',faculty.faculty,name='faculty'),path('faculty/<int:pk>/<str:kind>/<int:item>/',faculty.author,name='author'),path('faculty/quiz/<int:pk>/question/<int:item>/',faculty.question,name='question')]

from academics import degree_views
urlpatterns += [path('degree/',degree_views.degree,name='degree'),path('degree/graduate/',degree_views.graduate,name='graduate')]

from academics.gradebook_views import gradebook
urlpatterns += [path('courses/<int:pk>/gradebook/',gradebook,name='gradebook')]

from academics import operation_views as ov
urlpatterns += [path('inbox/',ov.inbox,name='inbox'),path('inbox/<int:pk>/read/',ov.mark_read,name='mark_read'),path('records/',ov.records,name='records'),path('reports/',ov.reports,name='reports')]

from academics import transcript_views as tv
urlpatterns += [path('transcripts/queue/',tv.transcript_queue,name='transcript_queue'),path('transcripts/issue/<int:pk>/',tv.issue,name='issue_transcript'),path('transcripts/<uuid:identifier>/',tv.transcript,name='transcript')]

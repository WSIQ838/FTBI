from django.conf import settings
from django.urls import include
from ftbi.login_security import LimitedLoginView
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from academics import views
urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LimitedLoginView.as_view(), name="login"),
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
from academics import exam_grading
urlpatterns += [path('quizzes/<int:pk>/policy/',exam_grading.exam_policy,name='exam_policy'),path('quizzes/<int:pk>/grading/',exam_grading.exam_queue,name='exam_queue'),path('attempts/<int:pk>/grade/',exam_grading.grade_attempt,name='grade_attempt')]
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

from academics.payment_views import payment_portal
urlpatterns += [path('payments/',payment_portal,name='payment_portal')]

from academics import discussion_views as dv
urlpatterns += [path('courses/<int:pk>/discussions/',dv.discussions,name='discussions'),path('discussions/<int:pk>/',dv.discussion,name='discussion'),path('password-reset/',auth_views.PasswordResetView.as_view(),name='password_reset'),path('password-reset/done/',auth_views.PasswordResetDoneView.as_view(),name='password_reset_done'),path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(),name='password_reset_confirm'),path('reset/done/',auth_views.PasswordResetCompleteView.as_view(),name='password_reset_complete')]

from academics import evaluation_views as ev
urlpatterns += [path('evaluations/',ev.evaluations,name='evaluations'),path('evaluations/<int:pk>/',ev.evaluate,name='evaluate')]

from academics import attachment_views as av
urlpatterns += [path('submissions/<int:pk>/attachment/upload/',av.upload_attachment,name='upload_attachment'),path('submissions/<int:pk>/attachment/',av.download_attachment,name='download_attachment')]

from ftbi import mfa
urlpatterns += [path('account/mfa/setup/',mfa.setup,name='mfa_setup'),path('account/mfa/verify/',mfa.verify,name='mfa_verify')]

if settings.FTBI_OIDC_ENABLED:
    urlpatterns += [path('oidc/',include('mozilla_django_oidc.urls'))]

from academics import experience
urlpatterns += [path('search/',experience.search,name='search'),path('notifications/',experience.notifications,name='notifications')]

from academics import public_admissions,pdf_records
urlpatterns += [path('apply/signup/',public_admissions.applicant_signup,name='applicant_signup'),path('transcripts/<uuid:identifier>/pdf/',pdf_records.transcript_pdf,name='transcript_pdf')]

from academics import checkout
urlpatterns += [path('payments/checkout/',checkout.checkout,name='checkout'),path('payments/webhook/',checkout.webhook,name='stripe_webhook')]

from academics import workspaces
urlpatterns += [path('workspaces/',workspaces.workspaces,name='workspaces'),path('reports/summary.csv',workspaces.institutional_csv,name='institutional_csv')]

from academics import assistant_views
urlpatterns += [path('assistant/',assistant_views.assistant,name='assistant')]

from academics import advisor_views,diploma_views
urlpatterns += [path('advising/',advisor_views.caseload,name='caseload'),path('advising/<int:pk>/',advisor_views.advise,name='advise'),path('diplomas/queue/',diploma_views.diploma_queue,name='diploma_queue'),path('diplomas/issue/<int:pk>/',diploma_views.issue_diploma,name='issue_diploma'),path('diplomas/<uuid:identifier>/pdf/',diploma_views.diploma_pdf,name='diploma_pdf')]

from academics import bank_views
urlpatterns += [path('question-bank/',bank_views.bank,name='question_bank'),path('quizzes/<int:pk>/bank-import/',bank_views.import_question,name='bank_import')]

from ftbi import health
urlpatterns += [path('health/live/',health.live,name='health_live'),path('health/ready/',health.ready,name='health_ready')]

from academics import admission_review,registration_lifecycle
urlpatterns += [path('admissions/review/',admission_review.review_queue,name='admission_review'),path('admissions/review/<int:pk>/decide/',admission_review.decide,name='admission_decide'),path('admissions/review/<int:pk>/activate/',admission_review.activate_student,name='activate_student'),path('admissions/<int:pk>/letter/',admission_review.decision_letter,name='decision_letter'),path('enrollment/<int:pk>/drop/',registration_lifecycle.drop,name='drop_course'),path('waitlist/<int:pk>/leave/',registration_lifecycle.leave_waitlist,name='leave_waitlist')]

urlpatterns += [path('apply/activate/<int:pk>/<str:token>/',public_admissions.activate,name='applicant_activate')]

from ftbi import recovery
urlpatterns += [path('account/recovery/codes/',recovery.generate,name='recovery_codes'),path('account/recovery/verify/',recovery.recover,name='mfa_recover')]

from academics import course_tools
from academics import policy_views
urlpatterns += [path('submission-revisions/<int:pk>/attachment/', policy_views.revision_attachment, name='revision_attachment')]
urlpatterns += [path('assignments/<int:pk>/policy/', policy_views.assignment_policy, name='assignment_policy'), path('assignments/<int:pk>/rubric/', policy_views.rubric, name='rubric'), path('submissions/<int:pk>/history/', policy_views.submission_history, name='submission_history')]
urlpatterns += [path('faculty/assignment/<int:pk>/bulk-grade/',course_tools.bulk_grade,name='bulk_grade'),path('faculty/<int:pk>/copy/',course_tools.copy_content,name='copy_content'),path('courses/<int:pk>/progress/',course_tools.progress,name='course_progress'),path('calendar/export.ics',course_tools.calendar_export,name='calendar_export')]

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
from academics import student_record_views as srv
urlpatterns += [path('registrar/final-grades/',srv.final_grade_queue,name='final_grade_queue'),path('registrar/final-grades/<int:pk>/release/',srv.release_final_grade,name='release_final_grade')]
urlpatterns += [path('enrollment/<int:pk>/withdraw/',srv.request_withdrawal,name='request_withdrawal'),path('registrar/withdrawals/',srv.withdrawals,name='withdrawal_queue'),path('registrar/withdrawals/<int:pk>/decide/',srv.decide_withdrawal,name='decide_withdrawal'),path('account/emergency-contacts/',srv.emergency_contacts,name='emergency_contacts'),path('account/records.json',srv.personal_export,name='personal_export'),path('standing/',srv.academic_standing,name='academic_standing'),path('registrar/standing/calculate/',srv.calculate_standing,name='calculate_standing'),path('registrar/enrollment/<int:pk>/grade/',srv.scaled_grade,name='scaled_final_grade'),path('records/enrollment-letter/',srv.issue_enrollment_letter,name='issue_enrollment_letter'),path('records/enrollment-letter/<uuid:identifier>/',srv.enrollment_letter,name='enrollment_letter')]
urlpatterns += [path('record/',rv.student_record,name='student_record'),path('catalog/',rv.catalog,name='catalog'),path('register/<int:pk>/',rv.register,name='register'),path('admissions/',rv.admissions,name='admissions')]

from academics.service_views import student_services
urlpatterns += [path('services/',student_services,name='student_services')]

from academics import quiz_views
from academics import exam_grading
urlpatterns += [path('quizzes/<int:pk>/policy/',exam_grading.exam_policy,name='exam_policy'),path('quizzes/<int:pk>/grading/',exam_grading.exam_queue,name='exam_queue'),path('attempts/<int:pk>/grade/',exam_grading.grade_attempt,name='grade_attempt')]
urlpatterns += [path('quizzes/',quiz_views.quizzes,name='quizzes'),path('quizzes/<int:pk>/',quiz_views.take_quiz,name='take_quiz')]

from academics import faculty
from academics import learning_views
urlpatterns += [path('faculty/<int:pk>/modules/<int:item>/',learning_views.module_editor,name='module_editor'),path('lessons/<int:pk>/complete/',learning_views.complete_lesson,name='complete_lesson'),path('faculty/<int:pk>/completion-policy/',learning_views.completion_policy,name='completion_policy'),path('courses/<int:pk>/certificate/',learning_views.issue_certificate,name='issue_course_certificate'),path('course-certificates/<uuid:identifier>/',learning_views.certificate_pdf,name='course_certificate'),path('courses/<int:pk>/attendance/',learning_views.attendance_analytics,name='attendance_analytics')]
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
from academics import billing_views
urlpatterns += [path('finance/',billing_views.finance,name='finance'),path('finance/invoices/new/',billing_views.new_invoice,name='new_invoice'),path('invoices/',billing_views.invoices,name='invoices'),path('invoices/<int:pk>/',billing_views.invoice,name='invoice'),path('finance/payments/<int:pk>/verify/',billing_views.verify_payment,name='verify_payment'),path('finance/invoices/<int:pk>/allocate/',billing_views.allocate,name='allocate_payment'),path('finance/invoices/<int:pk>/plan/',billing_views.plan,name='payment_plan'),path('finance/schedules/<int:pk>/bill/',billing_views.run_billing,name='run_billing'),path('payments/<int:pk>/receipt.pdf',billing_views.receipt,name='payment_receipt'),path('finance/reconciliation.csv',billing_views.reconciliation,name='financial_reconciliation')]
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
from academics import ai_admin_views
urlpatterns += [path('ai/configuration/',ai_admin_views.configuration,name='ai_configuration'),path('ai/usage/',ai_admin_views.usage,name='ai_usage')]
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
from academics import account_views
urlpatterns += [path('account/sessions/',account_views.sessions,name='account_sessions'),path('account/sessions/<int:pk>/revoke/',account_views.revoke_session,name='revoke_session'),path('account/security-control/',account_views.account_control,name='account_control'),path('account/notifications/',account_views.notification_history,name='notification_history'),path('account/notifications/preferences/',account_views.preferences,name='notification_preferences'),path('account/notifications/<int:pk>/read/',account_views.read_notification,name='read_notification'),path('account/password/',auth_views.PasswordChangeView.as_view(template_name='form.html',extra_context={'heading':'Change password'},success_url='/account/sessions/'),name='password_change')]
urlpatterns += [path('account/recovery/codes/',recovery.generate,name='recovery_codes'),path('account/recovery/verify/',recovery.recover,name='mfa_recover')]

from academics import course_tools
from academics import package_views
urlpatterns += [path('faculty/<int:pk>/export.json',package_views.export_package,name='export_course_package'),path('faculty/<int:pk>/import/',package_views.import_package,name='import_course_package')]
from academics import policy_views
urlpatterns += [path('submission-revisions/<int:pk>/attachment/', policy_views.revision_attachment, name='revision_attachment')]
urlpatterns += [path('assignments/<int:pk>/policy/', policy_views.assignment_policy, name='assignment_policy'), path('assignments/<int:pk>/rubric/', policy_views.rubric, name='rubric'), path('submissions/<int:pk>/history/', policy_views.submission_history, name='submission_history')]
urlpatterns += [path('faculty/assignment/<int:pk>/bulk-grade/',course_tools.bulk_grade,name='bulk_grade'),path('faculty/<int:pk>/copy/',course_tools.copy_content,name='copy_content'),path('courses/<int:pk>/progress/',course_tools.progress,name='course_progress'),path('calendar/export.ics',course_tools.calendar_export,name='calendar_export')]

from academics import document_views as dv,admissions_support_views as asv
urlpatterns += [path('documents/',dv.document_library,name='document_library'),path('documents/upload/<str:kind>/<int:pk>/',dv.upload_document,name='upload_document'),path('documents/<int:pk>/',dv.document_detail,name='document_detail'),path('documents/version/<int:pk>/download/',dv.document_download,name='document_download'),path('documents/version/<int:pk>/verify/',dv.verify_document,name='verify_document'),path('apply/recover/',public_admissions.resend_activation,name='resend_activation'),path('admissions/<int:pk>/details/',asv.application_details,name='application_details'),path('admissions/<int:pk>/note/',asv.application_note,name='application_note'),path('admissions/<int:pk>/reviewer/',asv.assign_reviewer,name='assign_reviewer'),path('admissions/<int:pk>/interview/',asv.schedule_interview,name='schedule_interview'),path('admissions/interview/<int:pk>/cancel/',asv.cancel_interview,name='cancel_interview'),path('admissions/conversions.csv',asv.conversion_report,name='admission_conversion_report')]

from academics import support_views as sv
urlpatterns += [path('support/',sv.support_home,name='support_home'),path('support/slots/new/',sv.create_slot,name='create_advisor_slot'),path('support/slots/<int:pk>/book/',sv.book_slot,name='book_advisor_slot'),path('support/slots/<int:pk>/close/',sv.close_slot,name='close_advisor_slot'),path('support/bookings/<int:pk>/change/',sv.change_booking,name='change_advisor_booking'),path('support/cases/new/',sv.create_case,name='create_support_case'),path('support/advisee/<int:assignment_pk>/case/',sv.create_case,name='create_advisee_case'),path('support/cases/<int:pk>/',sv.case_detail,name='support_case'),path('support/cases/<int:pk>/status/',sv.case_status,name='support_case_status'),path('support/cases/<int:pk>/action/<str:kind>/',sv.add_support_action,name='support_action'),path('support/intervention/<int:pk>/finish/',sv.finish_intervention,name='finish_intervention'),path('support/risk/review/',sv.flag_risk,name='flag_risk'),path('support/risk/<int:pk>/acknowledge/',sv.acknowledge_risk,name='acknowledge_risk'),path('support/accommodations/',sv.accommodations,name='accommodations'),path('support/accommodations/new/',sv.draft_accommodation,name='draft_accommodation'),path('support/accommodations/<int:pk>/review/',sv.review_accommodation,name='review_accommodation')]

from academics import institution_views as iv
urlpatterns += [path('institution/settings/',iv.institution_settings,name='institution_settings'),path('institution/logo/upload/',iv.upload_logo,name='upload_institution_logo'),path('institution/logo.png',iv.institution_logo,name='institution_logo'),path('account/preferences/',iv.preferences,name='preferences'),path('imports/<str:kind>/preview/',iv.import_preview,name='import_preview'),path('imports/batch/<int:pk>/',iv.import_detail,name='import_detail'),path('imports/batch/<int:pk>/commit/',iv.import_commit,name='import_commit')]

from academics import credential_views as cv
urlpatterns += [path('credentials/',cv.credential_list,name='credential_list'),path('credentials/finalize/',cv.finalize_legacy,name='finalize_legacy_credential'),path('credentials/<uuid:identifier>/pdf/',cv.credential_pdf,name='credential_pdf'),path('credentials/<uuid:identifier>/revoke/',cv.revoke_credential,name='revoke_credential'),path('credentials/<uuid:identifier>/reissue/',cv.reissue_credential,name='reissue_credential'),path('verify-credential/',cv.verify_credential,name='verify_credential')]

from academics import finance_adjustment_views as fav
urlpatterns += [path('payments/history/',fav.history,name='payment_history'),path('finance/payments/<int:pk>/<str:kind>/',fav.adjust,name='payment_adjustment'),path('finance/disputes/<int:pk>/resolve/',fav.resolve,name='resolve_payment_dispute'),path('finance/holds/evaluate/',fav.refresh_holds,name='refresh_financial_holds')]

from academics import scholarship_views as shv
urlpatterns += [path('scholarships/',shv.home,name='scholarships'),path('scholarships/fund/<int:pk>/apply/',shv.apply,name='apply_scholarship'),path('scholarships/application/<int:pk>/',shv.detail,name='scholarship_application'),path('scholarships/application/<int:pk>/decide/',shv.decide,name='decide_scholarship'),path('scholarships/award/<int:pk>/<str:action>/',shv.award_action,name='scholarship_award_action')]

from academics import report_builder_views as rbv
urlpatterns += [path('reports/builder/',rbv.builder,name='report_builder'),path('reports/builder/new/',rbv.create_report,name='create_institutional_report'),path('reports/builder/<int:pk>/',rbv.run_report,name='run_institutional_report'),path('reports/builder/<int:pk>/capture/',rbv.capture,name='capture_report_snapshot'),path('reports/snapshots/<int:pk>/',rbv.snapshot_detail,name='report_snapshot'),path('reports/snapshots/<int:pk>/review/',rbv.review,name='review_report_snapshot'),path('reports/review/',rbv.review_queue,name='report_review_queue'),path('leadership/<str:role>/',rbv.leadership,name='leadership_dashboard')]

from academics import governance_views as gv
urlpatterns += [path('policies/',gv.policies,name='policies'),path('policies/revision/<int:pk>/',gv.policy_detail,name='policy_detail'),path('policies/<int:pk>/propose/',gv.propose,name='propose_policy_revision'),path('policies/revision/<int:pk>/review/',gv.review,name='review_policy_revision'),path('policies/revision/<int:pk>/withdraw/',gv.withdraw,name='withdraw_policy_revision'),path('policies/revision/<int:pk>/acknowledge/',gv.acknowledge,name='acknowledge_policy'),path('account/demographics/',gv.demographics,name='demographics'),path('account/demographics/withdraw/',gv.withdraw_answers,name='withdraw_demographics'),path('reports/demographics/',gv.demographic_report,name='demographic_report')]

from ftbi import observability
from academics import monitoring_views
urlpatterns += [path("health/metrics/",observability.metrics,name="operation_metrics"),path("operations/",monitoring_views.operations,name="operations")]

from academics import withdrawal_appeals as wa
urlpatterns += [path("withdrawals/<int:pk>/appeal/",wa.submit_appeal,name="withdrawal_appeal"),path("registrar/withdrawal-appeals/",wa.appeal_queue,name="withdrawal_appeals"),path("registrar/withdrawal-appeals/<int:pk>/",wa.review_appeal,name="review_withdrawal_appeal")]

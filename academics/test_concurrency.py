"""Row-lock behavior must be exercised on PostgreSQL, never inferred from SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from django.test import TransactionTestCase, Client, skipUnlessDBFeature
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.utils import timezone
from .models import Department,Term,Course,Enrollment
from .quizzes import Quiz,Question,Attempt
from django.test import override_settings


@skipUnlessDBFeature("has_select_for_update")
class ExaminationConcurrencyTests(TransactionTestCase):
    def test_duplicate_simultaneous_attempt_is_recorded_once(self):
        teacher=get_user_model().objects.create_user("teacher")
        student=get_user_model().objects.create_user("student")
        d=Department.objects.create(name="Concurrent")
        t=Term.objects.create(name="Fall",starts=timezone.localdate(),ends=timezone.localdate())
        c=Course.objects.create(code="C",title="Concurrency",department=d,term=t,instructor=teacher,published=True)
        Enrollment.objects.create(course=c,student=student)
        quiz=Quiz.objects.create(course=c,title="Quiz",published=True,closes=timezone.now()+timedelta(days=1))
        q=Question.objects.create(quiz=quiz,prompt="True?",kind="boolean",answer_key=[True])
        clients=[Client(),Client()]
        for client in clients: client.force_login(student)
        barrier=Barrier(2)
        def submit(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(f"/quizzes/{quiz.pk}/",{"attempt_number":"1",f"q{q.pk}":"true"}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes=list(executor.map(submit,clients))
        self.assertEqual(sorted(codes),[302,403])
        self.assertEqual(Attempt.objects.filter(quiz=quiz).count(),1)


@skipUnlessDBFeature("has_select_for_update")
class AccountConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from .models import Program
        from .registrar import StudentProfile,RegistrationWindow
        self.teacher=get_user_model().objects.create_user("teacher")
        self.students=[get_user_model().objects.create_user(f"student{i}") for i in range(2)]
        d=Department.objects.create(name="Concurrent")
        p=Program.objects.create(name="Program",department=d)
        self.profiles=[StudentProfile.objects.create(user=s,program=p,student_number=str(s.pk),admitted_on=timezone.localdate()) for s in self.students]
        t=Term.objects.create(name="Fall",starts=timezone.localdate(),ends=timezone.localdate())
        self.course=Course.objects.create(code="C",title="Concurrency",department=d,term=t,instructor=self.teacher,published=True)
        self.window=RegistrationWindow.objects.create(course=self.course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),capacity=1)

    def simultaneous(self,action):
        barrier=Barrier(2)
        def run(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return action(index)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run,range(2)))

    def test_registration_cannot_overfill_last_seat(self):
        from .prerequisites import WaitlistEntry
        clients=[Client(),Client()]
        for client,student in zip(clients,self.students): client.force_login(student)
        self.assertEqual(self.simultaneous(lambda i: clients[i].post(f"/register/{self.window.pk}/").status_code),[302,302])
        self.assertEqual(Enrollment.objects.filter(course=self.course,active=True).count(),1)
        self.assertEqual(WaitlistEntry.objects.filter(course=self.course).count(),1)

    def test_document_uploads_cannot_exceed_shared_quota(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .documents import StorageQuota,DocumentVersion
        student=self.students[0]
        StorageQuota.objects.create(user=student,limit_bytes=7)
        clients=[Client(),Client()]
        for client in clients: client.force_login(student)
        def upload(index):
            return clients[index].post('/documents/upload/student/0/',{"title":"Synthetic","file":SimpleUploadedFile("test.txt",b"12345")}).status_code
        self.assertEqual(sorted(self.simultaneous(upload)),[200,302])
        self.assertEqual(DocumentVersion.objects.count(),1)

    def test_advisor_appointment_cannot_be_double_booked(self):
        from .advising import AdvisorAssignment
        from .student_support import AdvisorSlot,AdvisorBooking
        for profile in self.profiles: AdvisorAssignment.objects.create(student=profile,advisor=self.teacher)
        slot=AdvisorSlot.objects.create(advisor=self.teacher,starts=timezone.now()+timedelta(days=1),ends=timezone.now()+timedelta(days=1,hours=1),location="Synthetic")
        clients=[Client(),Client()]
        for client,student in zip(clients,self.students): client.force_login(student)
        codes=self.simultaneous(lambda i:clients[i].post(f'/support/slots/{slot.pk}/book/').status_code)
        self.assertEqual(sorted(codes),[302,403])
        self.assertEqual(AdvisorBooking.objects.filter(status="booked").count(),1)

    def test_retention_and_new_version_upload_do_not_deadlock_or_erase_latest(self):
        import hashlib
        from django.contrib.auth.models import Permission
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .documents import PrivateDocument,DocumentVersion
        from .file_retention import FileRetentionPolicy,propose_batch,apply_batch
        self.teacher.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        owner=self.students[0]
        owner.user_permissions.add(Permission.objects.get(content_type__app_label="academics",codename="change_fileretentionbatch"))
        document=PrivateDocument.objects.create(owner=owner,title="Synthetic version race",kind="student")
        for number in [1,2]: DocumentVersion.objects.create(document=document,number=number,original_name="test.txt",data=b"DATA",size=4,sha256=hashlib.sha256(b"DATA").hexdigest(),uploaded_by=owner)
        DocumentVersion.objects.filter(document=document).update(uploaded=timezone.now()-timedelta(days=100))
        policy=FileRetentionPolicy.objects.create(kind="student",enabled=True,minimum_age_days=30,approval_reference="SYNTHETIC")
        batch=propose_batch(policy,self.teacher,"Synthetic proposal")
        client=Client();client.force_login(owner)
        def action(index):
            if index==0: return apply_batch(batch,owner)
            return client.post(f"/documents/upload/version/{document.pk}/",{"title":"New","file":SimpleUploadedFile("new.txt",b"NEW")}).status_code
        self.assertEqual(self.simultaneous(action),[1,302])
        self.assertEqual(document.versions.count(),3)
        self.assertEqual(bytes(document.versions.get(number=3).data),b"NEW")
        self.assertEqual(document.versions.filter(purged_at__isnull=False).count(),1)

    def test_retention_batch_cannot_be_applied_twice_concurrently(self):
        import hashlib
        from django.contrib.auth.models import Permission
        from django.core.exceptions import ValidationError
        from .documents import PrivateDocument,DocumentVersion
        from .file_retention import FileRetentionPolicy,propose_batch,apply_batch
        from .operations import AuditEvent
        self.teacher.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        reviewer=self.students[1]
        reviewer.user_permissions.add(Permission.objects.get(content_type__app_label="academics",codename="change_fileretentionbatch"))
        document=PrivateDocument.objects.create(owner=self.students[0],title="Synthetic retention",kind="student")
        for number in [1,2]: DocumentVersion.objects.create(document=document,number=number,original_name="test.txt",data=b"DATA",size=4,sha256=hashlib.sha256(b"DATA").hexdigest(),uploaded_by=self.students[0])
        DocumentVersion.objects.filter(document=document).update(uploaded=timezone.now()-timedelta(days=100))
        policy=FileRetentionPolicy.objects.create(kind="student",enabled=True,minimum_age_days=30,approval_reference="SYNTHETIC")
        batch=propose_batch(policy,self.teacher,"Synthetic proposal")
        def apply(index):
            try: apply_batch(batch,reviewer);return "applied"
            except ValidationError: return "blocked"
        self.assertEqual(sorted(self.simultaneous(apply)),["applied","blocked"])
        self.assertEqual(DocumentVersion.objects.filter(purged_at__isnull=False).count(),1)
        self.assertEqual(AuditEvent.objects.filter(action="file_retention_applied").count(),1)

    def test_overlapping_corequisite_carts_cannot_split_or_overbook_capacity(self):
        from django.core.exceptions import ValidationError
        from .registrar import RegistrationWindow
        from .prerequisites import Prerequisite
        from .registration_cart import register_together
        other=Course.objects.create(code="CO",title="Corequisite",department=self.course.department,term=self.course.term,instructor=self.teacher,published=True)
        second=RegistrationWindow.objects.create(course=other,opens=self.window.opens,closes=self.window.closes,capacity=1)
        Prerequisite.objects.create(course=self.course,required_code=other.code,kind="corequisite")
        Prerequisite.objects.create(course=other,required_code=self.course.code,kind="corequisite")
        def submit(index):
            ids=[self.window.pk,second.pk]
            if index: ids.reverse()
            try: register_together(self.students[index],ids);return "registered"
            except ValidationError: return "blocked"
        self.assertEqual(sorted(self.simultaneous(submit)),["blocked","registered"])
        rows=list(Enrollment.objects.filter(active=True).values_list("student_id","course_id"))
        self.assertEqual(len(rows),2)
        self.assertEqual(len({student for student,course in rows}),1)

    def test_parallel_appeal_grants_record_withdrawal_once(self):
        from django.contrib.auth.models import Permission
        from .student_records import WithdrawalRequest,WithdrawalAppeal
        from .services import FinalGrade
        self.teacher.user_permissions.set(Permission.objects.filter(content_type__app_label="academics"))
        enrollment=Enrollment.objects.create(student=self.students[0],course=self.course)
        original=WithdrawalRequest.objects.create(enrollment=enrollment,reason="Request",status="denied",reviewed_by=self.students[1],reviewed_at=timezone.now())
        appeal=WithdrawalAppeal.objects.create(request=original,reason="Grounds",original_decision={"status":"denied","reviewed_by":self.students[1].pk},policy_snapshot={"approval_reference":"SYNTHETIC"})
        clients=[Client(),Client()]
        for client in clients: client.force_login(self.teacher)
        results=self.simultaneous(lambda index:clients[index].post(f"/registrar/withdrawal-appeals/{appeal.pk}/",{"decision":"granted","reason":"Independent review"}).status_code)
        self.assertEqual(sorted(results),[302,403])
        self.assertEqual(FinalGrade.objects.filter(student=self.profiles[0],course=self.course,letter="W").count(),1)

    def test_parallel_risk_checks_create_one_alert_and_notification(self):
        from django.contrib.auth.models import Permission
        from .advising import AdvisorAssignment
        from .student_records import AcademicStanding
        from .student_support import AtRiskAlert
        from .notification_models import DurableNotification
        from .risk_checks import check_assignment
        self.teacher.user_permissions.add(Permission.objects.get(content_type__app_label="academics",codename="view_advisorassignment"))
        assignment=AdvisorAssignment.objects.create(student=self.profiles[0],advisor=self.teacher)
        AcademicStanding.objects.create(student=self.profiles[0],term=self.course.term,gpa=1,status="probation",policy_snapshot={},calculated_by=self.teacher)
        self.assertEqual(sorted(self.simultaneous(lambda index:check_assignment(assignment.pk))),[False,True])
        self.assertEqual(AtRiskAlert.objects.count(),1)
        self.assertEqual(DurableNotification.objects.filter(deduplication_key__startswith="risk-alert:").count(),1)

    def test_simultaneous_policy_proposals_get_distinct_versions(self):
        from .governance import InstitutionPolicy,PolicyRevision,propose_revision
        policy=InstitutionPolicy.objects.create(code="synthetic-policy",title="Synthetic",kind="academic")
        versions=self.simultaneous(lambda index:propose_revision(policy,self.teacher,f"Synthetic proposal {index}",{},timezone.localdate()).version)
        self.assertEqual(sorted(versions),[1,2])
        self.assertEqual(PolicyRevision.objects.count(),2)

    def test_scholarship_awards_cannot_overcommit_shared_budget(self):
        from django.core.exceptions import ValidationError
        from .scholarships import ScholarshipFund,ScholarshipAward,submit_application,decide_application
        fund=ScholarshipFund.objects.create(code="BUDGET",name="Synthetic",term=self.course.term,description="Concurrent review",budget=100,maximum_award=80,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),published=True,approval_reference="Synthetic")
        applications=[submit_application(profile,fund,80,"Synthetic request") for profile in self.profiles]
        def approve(index):
            try:
                decide_application(applications[index],"approved","Reviewed",self.teacher,80)
                return "approved"
            except ValidationError: return "blocked"
        self.assertEqual(sorted(self.simultaneous(approve)),["approved","blocked"])
        self.assertEqual(ScholarshipAward.objects.count(),1)
        self.assertEqual(fund.committed,80)

    def test_refunds_cannot_reverse_more_than_original_payment(self):
        import uuid
        from django.core.exceptions import ValidationError
        from .payments import PaymentRequest
        from .billing import verify_manual_payment
        from .finance_adjustments import record_adjustment,PaymentAdjustment,net_payment
        payment=verify_manual_payment(PaymentRequest.objects.create(student=self.profiles[0],amount=100,reference="Synthetic confirmed payment"),self.teacher)
        def refund(index):
            try:
                record_adjustment(payment,"refund",60,f"synthetic-refund-{index}","Confirmed external refund",self.teacher,uuid.uuid4())
                return "recorded"
            except ValidationError: return "blocked"
        self.assertEqual(sorted(self.simultaneous(refund)),["blocked","recorded"])
        self.assertEqual(PaymentAdjustment.objects.count(),1)
        self.assertEqual(net_payment(payment),40)

    @override_settings(FTBI_STRIPE_ENABLED=True,STRIPE_WEBHOOK_SECRET="concurrent-test-secret")
    def test_simultaneous_signed_webhooks_credit_once(self):
        import json,time,hmac,hashlib
        from .payments import PaymentRequest
        from .services import LedgerEntry
        payment=PaymentRequest.objects.create(student=self.profiles[0],amount=25,reference="stripe:cs_concurrent")
        body=json.dumps({"type":"checkout.session.completed","data":{"object":{"id":"cs_concurrent","payment_status":"paid","metadata":{"ftbi_payment_id":str(payment.pk)},"currency":"usd","amount_total":2500}}}).encode()
        stamp=str(int(time.time())); signature=hmac.new(b"concurrent-test-secret",stamp.encode()+b"."+body,hashlib.sha256).hexdigest()
        clients=[Client(),Client()]
        self.assertEqual(self.simultaneous(lambda i: clients[i].post('/payments/webhook/',body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}').status_code),[200,200])
        self.assertEqual(LedgerEntry.objects.filter(student=self.profiles[0]).count(),1)
        self.assertEqual(LedgerEntry.objects.get().amount,-25)


@skipUnlessDBFeature("has_select_for_update")
@override_settings(FTBI_AI_MODEL="test-model")
class AIQuotaConcurrencyTests(TransactionTestCase):
    def test_parallel_requests_cannot_bypass_hourly_quota(self):
        from django.core.exceptions import ValidationError
        from .ai_governance import AIConfiguration,AIUsage,reserve_request
        user=get_user_model().objects.create_user("ai-user")
        AIConfiguration.objects.create(pk=1,enabled=True,monthly_budget=10,input_price_per_million=1,output_price_per_million=2,hourly_user_limit=1,policy_reference="Test")
        barrier=Barrier(2)
        def reserve(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try: reserve_request(user,"study","Question","Instructions")
                except ValidationError: return "blocked"
                return "reserved"
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor: outcomes=list(executor.map(reserve,range(2)))
        self.assertEqual(sorted(outcomes),["blocked","reserved"])
        self.assertEqual(AIUsage.objects.count(),1)

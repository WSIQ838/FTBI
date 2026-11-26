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

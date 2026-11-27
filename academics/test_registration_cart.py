from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Department,Program,Term,Course,Enrollment
from .registrar import StudentProfile,RegistrationWindow
from .prerequisites import Prerequisite,WaitlistEntry
from .registration_cart import register_together
from .notification_models import DurableNotification
from .student_records import WithdrawalRequest


class RegistrationCartTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.student=users.create_user("cart-student")
        self.other=users.create_user("cart-other")
        self.teacher=users.create_user("cart-teacher")
        department=Department.objects.create(name="Cart department")
        program=Program.objects.create(name="Cart program",department=department)
        self.profile=StudentProfile.objects.create(user=self.student,program=program,student_number="CART1",admitted_on=timezone.localdate())
        self.other_profile=StudentProfile.objects.create(user=self.other,program=program,student_number="CART2",admitted_on=timezone.localdate())
        self.term=Term.objects.create(name="Cart term",starts=timezone.localdate(),ends=timezone.localdate()+timedelta(days=90))
        self.courses=[Course.objects.create(code=code,title=code,department=department,term=self.term,instructor=self.teacher,published=True) for code in ["A","B"]]
        self.windows=[RegistrationWindow.objects.create(course=course,opens=timezone.now()-timedelta(days=1),closes=timezone.now()+timedelta(days=1),capacity=2) for course in self.courses]
        for course,other in [(self.courses[0],self.courses[1]),(self.courses[1],self.courses[0])]: Prerequisite.objects.create(course=course,required_code=other.code,kind="corequisite")
        self.ids=[window.pk for window in self.windows]
        self.client.force_login(self.student)

    def test_mutual_corequisites_register_atomically_and_replay_sends_no_duplicates(self):
        self.assertEqual(self.client.post(reverse("register",args=[self.windows[0].pk])).status_code,403)
        response=self.client.post(reverse("registration_cart"),{"courses":self.ids})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Enrollment.objects.filter(student=self.student,active=True).count(),2)
        self.assertEqual(register_together(self.student,self.ids),0)
        self.assertEqual(DurableNotification.objects.filter(user=self.student).count(),2)

    def test_full_course_rolls_back_every_enrollment_and_preserves_waitlist(self):
        self.windows[1].capacity=0;self.windows[1].save()
        entry=WaitlistEntry.objects.create(student=self.profile,course=self.courses[0])
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.assertFalse(Enrollment.objects.exists());self.assertTrue(WaitlistEntry.objects.filter(pk=entry.pk).exists())
        self.assertFalse(DurableNotification.objects.exists())

    def test_earlier_waitlist_entry_is_not_skipped(self):
        WaitlistEntry.objects.create(student=self.other_profile,course=self.courses[1])
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.assertFalse(Enrollment.objects.exists())
        self.assertEqual(WaitlistEntry.objects.count(),1)

    def test_batch_does_not_satisfy_prior_completion_requirement(self):
        Prerequisite.objects.filter(course=self.courses[0]).update(kind="prerequisite")
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.assertFalse(Enrollment.objects.exists())

    def test_closed_and_cross_term_courses_and_duplicate_sections_are_rejected(self):
        self.windows[1].closes=timezone.now()-timedelta(seconds=1);self.windows[1].save()
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.windows[1].closes=timezone.now()+timedelta(days=1);self.windows[1].save()
        self.courses[1].term=Term.objects.create(name="Different",starts=timezone.localdate(),ends=timezone.localdate());self.courses[1].save()
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.courses[1].term=self.term;self.courses[1].code="A";self.courses[1].section="02";self.courses[1].save()
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.assertFalse(Enrollment.objects.exists())

    def test_hold_and_approved_withdrawal_block_cart(self):
        self.profile.registration_hold=True;self.profile.save()
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.profile.registration_hold=False;self.profile.save()
        enrollment=Enrollment.objects.create(student=self.student,course=self.courses[0],active=False)
        WithdrawalRequest.objects.create(enrollment=enrollment,reason="Withdrawn",status="approved")
        with self.assertRaises(ValidationError): register_together(self.student,self.ids)
        self.assertFalse(Enrollment.objects.filter(active=True).exists())

    def test_queue_head_is_removed_only_on_success(self):
        WaitlistEntry.objects.create(student=self.profile,course=self.courses[0])
        self.assertEqual(register_together(self.student,self.ids),2)
        self.assertFalse(WaitlistEntry.objects.exists())

    def test_malformed_selection_and_missing_student_profile_cannot_register(self):
        for ids in [[],self.ids*2,list(range(11)),["1"],[999999]]:
            with self.assertRaises(ValidationError): register_together(self.student,ids)
        with self.assertRaises(ValidationError): register_together(self.teacher,self.ids)
        self.assertFalse(Enrollment.objects.exists())

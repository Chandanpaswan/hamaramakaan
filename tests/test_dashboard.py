from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.core.models import AuditLog
from apps.leads.models import Lead
from apps.properties.models import Property

from .factories import make_property, make_user


class AccessControlTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get("/manage/")
        self.assertRedirects(response, "/manage/login/?next=/manage/")

    def test_non_staff_cannot_log_in(self):
        get_user_model().objects.create_user("visitor", password="Str0ng-pass-123")
        response = self.client.post("/manage/login/", {"username": "visitor", "password": "Str0ng-pass-123"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not have dashboard access")

    def test_role_matrix_enforced_server_side(self):
        editor = make_user("editor", "Content Editor")
        self.client.force_login(editor)
        self.assertEqual(self.client.get("/manage/m/blog-posts/").status_code, 200)
        self.assertEqual(self.client.get("/manage/leads/").status_code, 403)
        self.assertEqual(self.client.get("/manage/properties/new/").status_code, 403)
        self.assertEqual(self.client.get("/manage/settings/").status_code, 403)

    def test_admin_cannot_grant_super_admin(self):
        admin = make_user("admin", "Admin")
        admin.user_permissions.add(*__import__("django.contrib.auth.models", fromlist=["Permission"]).Permission.objects.filter(
            codename__in=["add_user", "change_user"]))
        self.client.force_login(admin)
        form = self.client.get("/manage/users/new/").context["form"]
        self.assertNotIn("Super Admin", [g.name for g in form.fields["role"].queryset])


class LeadVisibilityTests(TestCase):
    def setUp(self):
        self.sales = make_user("sales", "Sales Executive")
        self.manager = make_user("manager", "Sales Manager")
        self.mine = Lead.objects.create(name="Mine", phone="+91 98100 00001", assigned_to=self.sales)
        self.other = Lead.objects.create(name="Other", phone="+91 98100 00002")

    def test_sales_executive_sees_only_assigned(self):
        self.client.force_login(self.sales)
        names = [l.name for l in self.client.get("/manage/leads/").context["page_obj"]]
        self.assertEqual(names, ["Mine"])
        self.assertEqual(self.client.get(f"/manage/leads/{self.other.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/manage/leads/export/").status_code, 403)

    def test_sales_executive_cannot_reassign(self):
        self.client.force_login(self.sales)
        response = self.client.post(f"/manage/leads/{self.mine.pk}/", {"form": "assign", "a-assigned_to": self.manager.pk})
        self.assertEqual(response.status_code, 403)

    def test_status_change_recorded(self):
        self.client.force_login(self.sales)
        self.client.post(f"/manage/leads/{self.mine.pk}/", {"form": "update", "u-status": "contacted", "u-priority": "high",
                                                           "u-requirement": "buy"})
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, "contacted")
        self.assertTrue(self.mine.status_history.filter(to_status="contacted").exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.STATUS).exists())

    def test_manager_assigns_and_exports_with_audit(self):
        self.client.force_login(self.manager)
        self.client.post(f"/manage/leads/{self.other.pk}/", {"form": "assign", "a-assigned_to": self.sales.pk})
        self.other.refresh_from_db()
        self.assertEqual(self.other.assigned_to, self.sales)
        self.assertEqual(self.other.assignments.count(), 1)

        Lead.objects.create(name="=HYPERLINK(\"http://evil\")", phone="+91 98100 00003")
        response = self.client.get("/manage/leads/export/")
        body = response.content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", body)  # spreadsheet formula injection neutralised
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.EXPORT).exists())


class ApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.prop = make_property(status=Property.Status.PENDING, source=Property.Source.OWNER, owner_email="o@example.com")

    def test_property_manager_approves(self):
        self.client.force_login(make_user("pm", "Property Manager"))
        self.client.post(f"/manage/properties/{self.prop.pk}/review/", {"action": "approve"})
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.status, Property.Status.PUBLISHED)
        self.assertIsNotNone(self.prop.published_at)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.APPROVE).exists())
        self.assertEqual(self.client.get(self.prop.get_absolute_url()).status_code, 200)

    def test_rejection_requires_reason(self):
        self.client.force_login(make_user("pm", "Property Manager"))
        self.client.post(f"/manage/properties/{self.prop.pk}/review/", {"action": "reject", "note": ""})
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.status, Property.Status.PENDING)

    def test_sales_cannot_approve(self):
        self.client.force_login(make_user("sales", "Sales Executive"))
        response = self.client.post(f"/manage/properties/{self.prop.pk}/review/", {"action": "approve"})
        self.assertEqual(response.status_code, 403)


class LoginLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        make_user("staff")

    def test_lockout_after_repeated_failures(self):
        with self.settings(LOGIN_FAILURE_LIMIT=3):
            for _ in range(3):
                self.client.post("/manage/login/", {"username": "staff", "password": "wrong"})
            response = self.client.post("/manage/login/", {"username": "staff", "password": "Str0ng-pass-123"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED).count(), 3)
        self.assertNotIn("wrong", "".join(AuditLog.objects.values_list("description", flat=True)))

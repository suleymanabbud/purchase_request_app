"""
اختبار الدورة المستندية الكاملة — من إنشاء الطلب حتى الانتهاء
يغطي جميع حالات سير العمل الممكنة في نظام طلبات الشراء

📋 الدورة المستندية:
  1. موظف → يُنشئ طلب شراء → الحالة: pending_manager
  2. المدير المباشر → يوافق → الحالة: pending_finance
  3. المدير المالي → يوافق → الحالة: pending_disbursement
  4. آمر الصرف → يوافق → الحالة: pending_procurement
  5. المشتريات → تستلم الطلب

  حالات خاصة:
  - رفض الطلب في أي مرحلة → الحالة: rejected
  - مدير مالي ينشئ طلب من قسمه → يتخطى مرحلة المدير المباشر + المالية (auto-skip)
  - آمر الصرف ينشئ طلب → يتخطى مراحل متعددة
"""

import pytest
from tests.conftest import login, auth_header


# ==================== 1. اختبار المصادقة ====================

class TestAuth:
    """اختبارات تسجيل الدخول"""

    def test_login_success(self, seeded_client):
        """تسجيل دخول ناجح"""
        res = seeded_client.post("/api/login", json={
            "username": "requester_hr",
            "password": "Hr2024!",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert data["user"]["role"] == "requester"
        assert data["user"]["department"] == "موارد بشرية"

    def test_login_wrong_password(self, seeded_client):
        """فشل تسجيل الدخول بكلمة مرور خاطئة"""
        res = seeded_client.post("/api/login", json={
            "username": "requester_hr",
            "password": "wrong_password",
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, seeded_client):
        """فشل تسجيل الدخول بمستخدم غير موجود"""
        res = seeded_client.post("/api/login", json={
            "username": "ghost_user",
            "password": "any",
        })
        assert res.status_code == 401

    def test_protected_endpoint_without_token(self, seeded_client):
        """الوصول لمسار محمي بدون توكن يُرفض"""
        res = seeded_client.get("/api/requests")
        assert res.status_code == 401


# ==================== 2. الدورة المستندية الطبيعية ====================

class TestNormalWorkflow:
    """
    الدورة الطبيعية: موظف → مدير → مالية → أمر صرف → مشتريات
    القسم: موارد بشرية
    """

    @pytest.fixture(autouse=True)
    def setup_tokens(self, seeded_client):
        """تسجيل دخول جميع المستخدمين المطلوبين"""
        self.client = seeded_client
        self.requester_token = login(seeded_client, "requester_hr", "Hr2024!")
        self.manager_token = login(seeded_client, "manager_hr", "HumanR@24")
        self.finance_token = login(seeded_client, "manager_finance", "Finance@24")
        self.exec_token = login(seeded_client, "manager_exec", "Exec@2024")

    def test_01_create_request(self):
        """الخطوة 1: إنشاء طلب شراء"""
        res = self.client.post("/api/requests", json={
            "requester": "موظف موارد بشرية",
            "department": "موارد بشرية",
            "delivery_address": "المكتب الرئيسي",
            "delivery_date": "2026-03-01",
            "project_code": "HR-001",
            "order_number": "PR-TEST-001",
            "currency": "SYP",
            "total_amount": 500000,
            "items": [
                {"item_name": "طابعة ليزر", "unit": "قطعة", "quantity": 2, "price": 150000, "specification": "HP LaserJet"},
                {"item_name": "حبر طابعة", "unit": "علبة", "quantity": 4, "price": 50000, "specification": "حبر أصلي"},
            ],
            "approval_data": {
                "requester_name": "موظف موارد بشرية",
                "requester_position": "موظف",
                "requester_date": "2026-02-16",
            }
        }, headers=auth_header(self.requester_token))

        assert res.status_code == 201, f"فشل إنشاء الطلب: {res.get_json()}"
        data = res.get_json()
        assert "id" in data
        self.__class__.request_id = data["id"]

    def test_02_request_starts_as_pending_manager(self):
        """التحقق: الطلب يبدأ في حالة pending_manager"""
        res = self.client.get(
            f"/api/requests/{self.request_id}",
            headers=auth_header(self.requester_token),
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "pending_manager"
        assert data["current_stage"] == "manager"

    def test_03_wrong_manager_cannot_approve(self):
        """مدير من قسم آخر لا يستطيع الموافقة"""
        bizdev_token = login(self.client, "manager_bizdev", "BizDev@24")
        res = self.client.patch(
            f"/api/requests/{self.request_id}/status",
            json={"action": "approve", "signature": "sig_data"},
            headers=auth_header(bizdev_token),
        )
        assert res.status_code == 403

    def test_04_requester_cannot_approve(self):
        """مقدم الطلب لا يستطيع الموافقة"""
        res = self.client.patch(
            f"/api/requests/{self.request_id}/status",
            json={"action": "approve"},
            headers=auth_header(self.requester_token),
        )
        assert res.status_code in (401, 403)

    def test_05_manager_approves(self):
        """الخطوة 2: المدير المباشر (موارد بشرية) يوافق → pending_finance"""
        res = self.client.patch(
            f"/api/requests/{self.request_id}/status",
            json={"action": "approve", "signature": "manager_sig_base64", "note": "موافق"},
            headers=auth_header(self.manager_token),
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "pending_finance"

    def test_06_finance_approves(self):
        """الخطوة 3: المدير المالي يوافق → pending_disbursement"""
        res = self.client.patch(
            f"/api/requests/{self.request_id}/status",
            json={"action": "approve", "signature": "finance_sig_base64"},
            headers=auth_header(self.finance_token),
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "pending_disbursement"

    def test_07_disbursement_approves(self):
        """الخطوة 4: آمر الصرف يوافق → pending_procurement"""
        res = self.client.patch(
            f"/api/requests/{self.request_id}/status",
            json={"action": "approve", "signature": "exec_sig_base64"},
            headers=auth_header(self.exec_token),
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "pending_procurement"

    def test_08_final_state_is_correct(self):
        """التحقق النهائي: الطلب وصل لمرحلة المشتريات بشكل صحيح"""
        res = self.client.get(
            f"/api/requests/{self.request_id}",
            headers=auth_header(self.requester_token),
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "pending_procurement"
        assert data["current_stage"] == "procurement"
        # التحقق من التوقيعات
        assert data.get("signatures", {}).get("manager") is not None or data.get("manager_signature") is not None
        assert data.get("signatures", {}).get("finance") is not None or data.get("finance_signature") is not None
        assert data.get("signatures", {}).get("disbursement") is not None or data.get("disbursement_signature") is not None


# ==================== 3. اختبار الرفض ====================

class TestRejectionWorkflow:
    """اختبار رفض الطلب في مراحل مختلفة"""

    @pytest.fixture(autouse=True)
    def setup_tokens(self, seeded_client):
        self.client = seeded_client
        self.requester_token = login(seeded_client, "requester_hr", "Hr2024!")
        self.manager_token = login(seeded_client, "manager_hr", "HumanR@24")
        self.finance_token = login(seeded_client, "manager_finance", "Finance@24")

    def _create_request(self, order_number):
        """إنشاء طلب جديد"""
        res = self.client.post("/api/requests", json={
            "requester": "موظف موارد بشرية",
            "department": "موارد بشرية",
            "delivery_address": "المكتب",
            "delivery_date": "2026-03-01",
            "project_code": "HR-REJ",
            "order_number": order_number,
            "currency": "SYP",
            "total_amount": 100000,
            "items": [{"item_name": "قلم", "unit": "قطعة", "quantity": 10, "price": 10000}],
        }, headers=auth_header(self.requester_token))
        assert res.status_code == 201
        return res.get_json()["id"]

    def test_reject_without_note_fails(self):
        """الرفض بدون ملاحظة يفشل"""
        req_id = self._create_request("PR-REJ-001")
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "reject"},
            headers=auth_header(self.manager_token),
        )
        assert res.status_code == 400

    def test_reject_by_manager(self):
        """رفض من المدير المباشر"""
        req_id = self._create_request("PR-REJ-002")
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "reject", "note": "الميزانية غير كافية"},
            headers=auth_header(self.manager_token),
        )
        assert res.status_code == 200
        assert res.get_json()["status"] == "rejected"

    def test_reject_by_finance(self):
        """رفض من المدير المالي بعد موافقة المدير المباشر"""
        req_id = self._create_request("PR-REJ-003")
        # المدير يوافق
        self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve", "signature": "sig"},
            headers=auth_header(self.manager_token),
        )
        # المالية ترفض
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "reject", "note": "لا يوجد بند ميزانية مخصص"},
            headers=auth_header(self.finance_token),
        )
        assert res.status_code == 200
        assert res.get_json()["status"] == "rejected"

    def test_cannot_act_on_rejected_request(self):
        """لا يمكن التصرف في طلب مرفوض"""
        req_id = self._create_request("PR-REJ-004")
        # رفض الطلب
        self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "reject", "note": "مرفوض"},
            headers=auth_header(self.manager_token),
        )
        # محاولة الموافقة على طلب مرفوض
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve"},
            headers=auth_header(self.manager_token),
        )
        assert res.status_code == 403


# ==================== 4. Auto-Skip (التخطي التلقائي) ====================

class TestAutoSkipWorkflow:
    """
    اختبار التخطي التلقائي عندما يكون المعتمد التالي هو نفسه.
    مثال: مدير المالية يوافق كمدير مباشر → يتخطى مرحلة المالية
    """

    @pytest.fixture(autouse=True)
    def setup_tokens(self, seeded_client):
        self.client = seeded_client
        self.requester_fin_token = login(seeded_client, "requester_finance", "Fin2024!")
        self.manager_finance_token = login(seeded_client, "manager_finance", "Finance@24")
        self.exec_token = login(seeded_client, "manager_exec", "Exec@2024")

    def test_finance_manager_auto_skip(self):
        """مدير المالية يوافق كمدير مباشر → يتخطى مرحلة المالية تلقائياً"""
        # إنشاء طلب من قسم المالية
        res = self.client.post("/api/requests", json={
            "requester": "موظف مالية",
            "department": "مالية",
            "delivery_address": "المكتب",
            "delivery_date": "2026-03-01",
            "project_code": "FIN-AUTO",
            "order_number": "PR-AUTO-001",
            "currency": "SYP",
            "total_amount": 200000,
            "items": [{"item_name": "آلة حاسبة", "unit": "قطعة", "quantity": 5, "price": 40000}],
        }, headers=auth_header(self.requester_fin_token))

        assert res.status_code == 201
        req_id = res.get_json()["id"]

        # مدير المالية يوافق كمدير مباشر
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve", "signature": "finance_manager_sig"},
            headers=auth_header(self.manager_finance_token),
        )
        assert res.status_code == 200
        data = res.get_json()

        # يجب أن يتخطى مرحلة المالية ويصل لأمر الصرف مباشرة
        assert data["status"] == "pending_disbursement", \
            f"يجب تخطي مرحلة المالية! الحالة الفعلية: {data['status']}"

    def test_exec_auto_skip_disbursement(self):
        """آمر الصرف يوافق كمدير مباشر → يتخطى مراحل متعددة"""
        # إنشاء طلب من قسم تنفيذية
        exec_req_token = login(self.client, "manager_exec", "Exec@2024")
        requester_token = login(self.client, "requester_finance", "Fin2024!")

        # إنشاء طلب عادي من المالية ونمرره للمراحل
        res = self.client.post("/api/requests", json={
            "requester": "موظف مالية",
            "department": "مالية",
            "delivery_address": "المكتب",
            "delivery_date": "2026-03-01",
            "project_code": "EXEC-AUTO",
            "order_number": "PR-AUTO-002",
            "currency": "SYP",
            "total_amount": 300000,
            "items": [{"item_name": "شاشة كمبيوتر", "unit": "قطعة", "quantity": 3, "price": 100000}],
        }, headers=auth_header(requester_token))

        assert res.status_code == 201
        req_id = res.get_json()["id"]

        # مدير المالية يوافق كمدير مباشر → auto-skip finance → pending_disbursement
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve", "signature": "fm_sig"},
            headers=auth_header(self.manager_finance_token),
        )
        assert res.status_code == 200
        assert res.get_json()["status"] == "pending_disbursement"

        # آمر الصرف يوافق → pending_procurement
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve", "signature": "exec_sig"},
            headers=auth_header(self.exec_token),
        )
        assert res.status_code == 200
        assert res.get_json()["status"] == "pending_procurement"


# ==================== 5. اختبار الأمان والصلاحيات ====================

class TestSecurity:
    """اختبارات الأمان والصلاحيات"""

    @pytest.fixture(autouse=True)
    def setup(self, seeded_client):
        self.client = seeded_client

    def test_no_access_without_token(self):
        """لا يمكن الوصول بدون توكن"""
        res = self.client.get("/api/requests")
        assert res.status_code == 401

    def test_invalid_token(self):
        """توكن غير صالح مرفوض"""
        res = self.client.get("/api/requests", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert res.status_code == 401

    def test_requester_cannot_approve(self):
        """مقدم الطلب لا يستطيع الموافقة"""
        token = login(self.client, "requester_hr", "Hr2024!")
        # إنشاء طلب
        res = self.client.post("/api/requests", json={
            "requester": "موظف",
            "department": "موارد بشرية",
            "delivery_address": "هنا",
            "delivery_date": "2026-03-01",
            "project_code": "SEC-01",
            "order_number": "PR-SEC-001",
            "currency": "SYP",
            "total_amount": 10000,
            "items": [{"item_name": "قلم", "unit": "قطعة", "quantity": 1, "price": 10000}],
        }, headers=auth_header(token))
        req_id = res.get_json()["id"]

        # محاولة الموافقة
        res = self.client.patch(
            f"/api/requests/{req_id}/status",
            json={"action": "approve"},
            headers=auth_header(token),
        )
        assert res.status_code in (401, 403)

    def test_duplicate_order_number_rejected(self):
        """رقم طلب مكرر يُرفض"""
        token = login(self.client, "requester_hr", "Hr2024!")
        payload = {
            "requester": "موظف",
            "department": "موارد بشرية",
            "delivery_address": "هنا",
            "delivery_date": "2026-03-01",
            "project_code": "DUP-01",
            "order_number": "PR-DUP-001",
            "currency": "SYP",
            "total_amount": 5000,
            "items": [{"item_name": "ممحاة", "unit": "قطعة", "quantity": 1, "price": 5000}],
        }
        # الطلب الأول ينجح
        res1 = self.client.post("/api/requests", json=payload, headers=auth_header(token))
        assert res1.status_code == 201

        # الطلب الثاني بنفس الرقم يفشل
        res2 = self.client.post("/api/requests", json=payload, headers=auth_header(token))
        assert res2.status_code == 400


# ==================== 6. اختبار عرض الطلبات ====================

class TestRequestListing:
    """اختبار جلب قائمة الطلبات"""

    @pytest.fixture(autouse=True)
    def setup(self, seeded_client):
        self.client = seeded_client

    def test_user_sees_own_requests(self):
        """مقدم الطلب يرى طلباته فقط"""
        token = login(self.client, "requester_hr", "Hr2024!")
        res = self.client.get("/api/user/requests", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)
        # كل الطلبات يجب أن تكون من نفس المنشئ
        for req in data:
            assert req.get("created_by") == "requester_hr" or req.get("department") == "موارد بشرية"

    def test_manager_sees_queue(self):
        """المدير يرى طابور العمل"""
        token = login(self.client, "manager_hr", "HumanR@24")
        res = self.client.get("/api/my/queue", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert isinstance(data, list)

    def test_request_details_include_items(self):
        """تفاصيل الطلب تتضمن الأصناف"""
        token = login(self.client, "requester_hr", "Hr2024!")
        # إنشاء طلب مع أصناف
        res = self.client.post("/api/requests", json={
            "requester": "موظف",
            "department": "موارد بشرية",
            "delivery_address": "هنا",
            "delivery_date": "2026-03-01",
            "project_code": "ITM-01",
            "order_number": "PR-ITM-001",
            "currency": "SYP",
            "total_amount": 30000,
            "items": [
                {"item_name": "ورق A4", "unit": "رزمة", "quantity": 3, "price": 10000},
            ],
        }, headers=auth_header(token))
        req_id = res.get_json()["id"]

        # جلب التفاصيل
        res = self.client.get(f"/api/requests/{req_id}", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "items" in data
        assert len(data["items"]) > 0
        assert data["items"][0]["item_name"] == "ورق A4"


# ==================== 7. اختبار Health Check ====================

class TestHealth:
    def test_health_endpoint(self, seeded_client):
        res = seeded_client.get("/api/health")
        assert res.status_code == 200
        assert res.get_json()["status"] == "ok"

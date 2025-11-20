from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from datetime import datetime
from .database import Base

# حالات سير العمل المؤتمت
WORKFLOW_STATUSES = (
    "pending_manager",       # بانتظار المدير المباشر
    "pending_finance",       # بانتظار المالية
    "pending_disbursement",  # بانتظار أمر الصرف
    "pending_procurement",   # بانتظار قسم المشتريات
    "completed",             # مكتمل بعد إنهاء قسم المشتريات
    "approved",              # معتمد نهائيًا (تقليدي)
    "rejected",              # مرفوض
)

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))  # admin, manager, finance, disbursement, requester
    department: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    requester: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255))
    delivery_address: Mapped[str] = mapped_column(String(255))
    delivery_date: Mapped[str] = mapped_column(String(50))  # نخزنها كنص ISO لتبسيط الأمثلة
    project_code: Mapped[str] = mapped_column(String(100))
    order_number: Mapped[str] = mapped_column(String(100), index=True, unique=True)
    currency: Mapped[str] = mapped_column(String(10))
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="pending_manager")  # pending_manager, pending_finance, pending_disbursement, pending_procurement, approved, rejected, completed
    current_stage: Mapped[str] = mapped_column(String(50), default="manager")  # manager | finance | disbursement | procurement | done
    next_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="manager")  # يُحدّد من سيعمل الآن
    procurement_status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | purchased | adjusted | cancelled
    procurement_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    procurement_assigned_to: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    procurement_completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    procurement_updated_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    rejection_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=True)  # اربطه بمستخدم المنشئ
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # بيانات جدول الموافقات
    requester_name: Mapped[str] = mapped_column(String(255), nullable=True)
    requester_position: Mapped[str] = mapped_column(String(255), nullable=True)
    manager_name: Mapped[str] = mapped_column(String(255), nullable=True)
    manager_position: Mapped[str] = mapped_column(String(255), nullable=True)
    finance_name: Mapped[str] = mapped_column(String(255), nullable=True)
    finance_position: Mapped[str] = mapped_column(String(255), nullable=True)
    disbursement_name: Mapped[str] = mapped_column(String(255), nullable=True)
    disbursement_position: Mapped[str] = mapped_column(String(255), nullable=True)
    requester_date: Mapped[str] = mapped_column(String(50), nullable=True)
    manager_date: Mapped[str] = mapped_column(String(50), nullable=True)
    finance_date: Mapped[str] = mapped_column(String(50), nullable=True)
    disbursement_date: Mapped[str] = mapped_column(String(50), nullable=True)

    items: Mapped[list["PurchaseItem"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    history: Mapped[list["ApprovalHistory"]] = relationship("ApprovalHistory", back_populates="request", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="request", cascade="all, delete-orphan")

class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"))
    item_name: Mapped[str] = mapped_column(String(255))
    specification: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(50))
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)

    request: Mapped["PurchaseRequest"] = relationship(back_populates="items")

class AccountType(Base):
    __tablename__ = "account_types"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("account_types.id"), nullable=True, index=True)  # حساب الأب
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # العلاقة مع الحساب الأب
    parent: Mapped[Optional["AccountType"]] = relationship("AccountType", remote_side=[id], foreign_keys=[parent_id], back_populates="children")
    children: Mapped[list["AccountType"]] = relationship("AccountType", foreign_keys=[parent_id], back_populates="parent")

class ApprovalHistory(Base):
    __tablename__ = "approval_history"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id", ondelete="CASCADE"), index=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)  # manager / finance / disbursement / admin
    actor_user: Mapped[str] = mapped_column(String(120), nullable=True)  # اسم المستخدم/الإيميل
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # approve / reject / create
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped["PurchaseRequest"] = relationship("PurchaseRequest", back_populates="history")

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    recipient_username: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    action_type: Mapped[str] = mapped_column(String(50))  # approve | reject | modify | info | procurement
    actor_username: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped[Optional["PurchaseRequest"]] = relationship("PurchaseRequest", back_populates="notifications")

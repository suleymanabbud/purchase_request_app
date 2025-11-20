from database import SessionLocal, Base, engine
from models import PurchaseRequest, PurchaseItem, ApprovalHistory, User

# حذف جميع البيانات من الجداول
def reset_all():
    db = SessionLocal()
    try:
        db.query(ApprovalHistory).delete()
        db.query(PurchaseItem).delete()
        db.query(PurchaseRequest).delete()
        db.query(User).delete()
        db.commit()
        print("تم حذف جميع البيانات بنجاح.")
    except Exception as e:
        db.rollback()
        print("حدث خطأ:", e)
    finally:
        db.close()

if __name__ == "__main__":
    reset_all()

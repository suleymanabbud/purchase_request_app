"""
أدوات لقراءة ملفات Excel وتحويلها إلى أنواع حسابات
"""
import os
from typing import List, Dict
from ..models import AccountType
from ..database import SessionLocal

# استيراد pandas بشكل اختياري
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

def parse_excel_account_types(file_path: str) -> List[Dict]:
    """
    قراءة ملف Excel وتحويله إلى قائمة أنواع حسابات
    
    توقع أن يحتوي الملف على الأعمدة التالية:
    - ID: رقم الحساب
    - Name: اسم الحساب بالعربية
    - Name_EN: اسم الحساب بالإنجليزية
    - Description: وصف الحساب (اختياري)
    - Parent_ID: رقم الحساب الأب (اختياري)
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas غير مثبت. يرجى تثبيته باستخدام: pip install pandas openpyxl")
    try:
        # قراءة ملف Excel
        df = pd.read_excel(file_path)
        
        # التحقق من وجود الأعمدة المطلوبة
        required_columns = ['ID', 'Name', 'Name_EN']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"الأعمدة المطلوبة مفقودة: {missing_columns}")
        
        # تحويل البيانات إلى قائمة
        account_types = []
        for _, row in df.iterrows():
            account_type = {
                'id': int(row['ID']),
                'name': str(row['Name']).strip(),
                'name_en': str(row['Name_EN']).strip(),
                'description': str(row.get('Description', '')).strip() if 'Description' in df.columns else '',
                'parent_id': int(row.get('Parent_ID', 0)) if 'Parent_ID' in df.columns and pd.notna(row.get('Parent_ID')) else None
            }
            account_types.append(account_type)
        
        return account_types
        
    except Exception as e:
        raise Exception(f"خطأ في قراءة ملف Excel: {str(e)}")

def save_account_types_to_db(account_types: List[Dict]) -> bool:
    """
    حفظ أنواع الحسابات في قاعدة البيانات
    """
    db = SessionLocal()
    try:
        # حذف البيانات القديمة
        db.query(AccountType).delete()
        
        # إضافة البيانات الجديدة
        for account_data in account_types:
            account_type = AccountType(
                id=account_data['id'],
                name=account_data['name'],
                name_en=account_data['name_en'],
                description=account_data.get('description', ''),
                parent_id=account_data.get('parent_id'),
                is_active=True
            )
            db.add(account_type)
        
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        raise Exception(f"خطأ في حفظ البيانات: {str(e)}")
    finally:
        db.close()

def process_excel_file(file_path: str) -> Dict:
    """
    معالجة ملف Excel كاملاً وحفظه في قاعدة البيانات
    """
    try:
        # قراءة البيانات من Excel
        account_types = parse_excel_account_types(file_path)
        
        # حفظ البيانات في قاعدة البيانات
        save_account_types_to_db(account_types)
        
        return {
            'success': True,
            'message': f'تم تحميل {len(account_types)} نوع حساب بنجاح',
            'count': len(account_types),
            'data': account_types
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }

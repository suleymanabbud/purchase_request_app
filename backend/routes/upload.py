"""
إدارة رفع الملفات
"""
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from ..utils.auth import require_auth_and_roles, require_auth
from ..utils.excel_parser import process_excel_file

bp = Blueprint("upload", __name__, url_prefix="/api")

# إعدادات رفع الملفات
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
UPLOAD_FOLDER = 'backend/uploads'

def allowed_file(filename):
    """التحقق من نوع الملف المسموح"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.post("/upload/account-types")
@require_auth_and_roles("admin")
def upload_account_types():
    """
    رفع ملف Excel لأنواع الحسابات
    """
    try:
        # التحقق من وجود الملف
        if 'file' not in request.files:
            return jsonify({'error': 'لم يتم رفع أي ملف'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'نوع الملف غير مدعوم. يرجى رفع ملف Excel (.xlsx أو .xls)'}), 400
        
        # إنشاء مجلد الرفع إذا لم يكن موجوداً
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # حفظ الملف
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # معالجة الملف
        result = process_excel_file(file_path)
        
        # حذف الملف المؤقت
        try:
            os.remove(file_path)
        except:
            pass
        
        if result['success']:
            return jsonify({
                'message': result['message'],
                'count': result['count'],
                'account_types': result['data']
            }), 200
        else:
            return jsonify({'error': result['message']}), 400
            
    except Exception as e:
        return jsonify({'error': f'خطأ في رفع الملف: {str(e)}'}), 500

@bp.get("/account-types")
@require_auth
def get_account_types():
    """
    جلب جميع أنواع الحسابات من قاعدة البيانات
    """
    from ..database import SessionLocal
    from ..models import AccountType
    
    db = SessionLocal()
    try:
        account_types = db.query(AccountType).filter(AccountType.is_active == True).all()
        
        result = []
        for account_type in account_types:
            result.append({
                "id": account_type.id,
                "name": account_type.name,
                "name_en": account_type.name_en,
                "description": account_type.description,
                "parent_id": account_type.parent_id,
                "parent_name": account_type.parent.name if account_type.parent else None,
                "is_root": account_type.parent_id is None
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"خطأ في جلب أنواع الحسابات: {str(e)}"}), 500
    finally:
        db.close()

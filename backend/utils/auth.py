try:
    import jwt
except ImportError:
    jwt = None
    print("⚠️ تحذير: مكتبة PyJWT غير مثبتة. سيتم استخدام Debug Mode فقط.")

import datetime
from functools import wraps
from flask import request, jsonify, current_app

# مفتاح سري للتوقيع (يجب تغييره في الإنتاج)
SECRET_KEY = "your-secret-key-change-in-production"

def create_token(user_id, username, role, department=None):
    """إنشاء JWT token للمستخدم"""
    if jwt is None:
        return None
    try:
        payload = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'department': department,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    except Exception as e:
        print(f"خطأ في إنشاء Token: {e}")
        return None

def verify_token(token):
    """التحقق من صحة الـ token"""
    if jwt is None:
        print("⚠️ JWT library not available - Debug Mode enabled")
        return None
    
    if not token or token == "null" or token == "undefined":
        print("❌ Invalid token value")
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        print("❌ Token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid token: {e}")
        return None
    except Exception as e:
        print(f"❌ Error verifying token: {e}")
        return None

def require_auth(f):
    """ديكوريتر للتحقق من المصادقة"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # دعم Debug Role للتطوير
        debug_role = request.headers.get('X-Debug-Role')
        if debug_role:
            print(f"🔧 Debug Mode: استخدام دور {debug_role}")
            request.user = {"role": debug_role, "username": debug_role, "user_id": 1}
            return f(*args, **kwargs)
        
        if not token:
            return jsonify({'error': 'Token مطلوب'}), 401
        
        user_data = verify_token(token)
        if not user_data:
            return jsonify({'error': 'Token غير صالح أو منتهي الصلاحية'}), 401
        
        # إضافة بيانات المستخدم للطلب
        request.user = user_data
        return f(*args, **kwargs)
    
    return decorated

def require_roles(*allowed_roles):
    """ديكوريتر للتحقق من الصلاحيات"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({'error': 'يجب تسجيل الدخول أولاً'}), 401
            
            user_role = request.user.get('role')
            if user_role not in allowed_roles:
                return jsonify({'error': 'ليس لديك صلاحية للوصول لهذا المورد'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def require_auth_and_roles(*allowed_roles):
    """ديكوريتر مشترك للمصادقة والصلاحيات"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                # دعم Debug Role للتطوير (أولوية)
                debug_role = request.headers.get('X-Debug-Role')
                if debug_role:
                    print(f"🔧 Debug Mode: استخدام دور {debug_role}")
                    if debug_role not in allowed_roles:
                        print(f"❌ Debug Role {debug_role} not in {allowed_roles}")
                        return jsonify({'error': f'Debug Role {debug_role} غير مسموح. المطلوب: {allowed_roles}'}), 403
                    request.user = {"role": debug_role, "username": debug_role, "user_id": 1}
                    return f(*args, **kwargs)
                
                # التحقق من المصادقة
                token = None
                auth_header = request.headers.get('Authorization')
                
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                
                # إذا لم يكن هناك token ولا JWT library، استخدم Debug Mode
                if not token and jwt is None:
                    print("⚠️ لا يوجد token ومكتبة JWT غير متاحة. الرجاء استخدام X-Debug-Role header")
                    return jsonify({'error': 'Token مطلوب أو استخدم X-Debug-Role header للتطوير'}), 401
                
                if not token:
                    print("❌ No token provided")
                    return jsonify({'error': 'Token مطلوب'}), 401
                
                print(f"✅ Verifying token...")
                user_data = verify_token(token)
                if not user_data:
                    print("❌ Token verification failed")
                    return jsonify({'error': 'Token غير صالح أو منتهي الصلاحية'}), 401
                
                print(f"✅ User authenticated: {user_data.get('username')}, Role: {user_data.get('role')}")
                
                # التحقق من الصلاحيات
                user_role = user_data.get('role')
                if user_role not in allowed_roles:
                    print(f"❌ Role check failed: {user_role} not in {allowed_roles}")
                    return jsonify({'error': f'ليس لديك صلاحية للوصول لهذا المورد. دورك: {user_role}, المطلوب: {allowed_roles}'}), 403
                
                # إضافة بيانات المستخدم للطلب
                request.user = user_data
                return f(*args, **kwargs)
            except Exception as e:
                print(f"❌ Exception in auth: {e}")
                return jsonify({'error': f'خطأ في المصادقة: {str(e)}'}), 500
        return decorated
    return decorator

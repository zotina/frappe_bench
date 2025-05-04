import frappe
import jwt
import redis
from functools import wraps
from frappe import _

JWT_SECRET = frappe.conf.get("jwt_secret")
JWT_ALGORITHM = "HS256"
REDIS_CLIENT = redis.Redis.from_url(frappe.conf.get("redis_cache"))
BLACKLIST_KEY_PREFIX = "jwt_blacklist:"

def validate_jwt(func):
    """
    Décorateur pour valider le token JWT dans l'en-tête Authorization.
    Exemple d'en-tête attendu : Authorization: Bearer <jwt_token>
    Vérifie également si le token est dans la liste noire de Redis.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = frappe.request.headers.get("Authorization")
        if not auth_header:
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Missing Authorization Header")
            return

        if not auth_header.startswith("Bearer "):
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Invalid Authorization Header. Use Bearer <token>")
            return

        token = auth_header.split(" ")[1]

        # Vérifier si le token est dans la liste noire
        redis_key = f"{BLACKLIST_KEY_PREFIX}{token}"
        try:
            if REDIS_CLIENT.exists(redis_key):
                frappe.local.response["http_status_code"] = 401
                frappe.local.response["message"] = _("Token has been blacklisted")
                return
        except redis.RedisError as e:
            frappe.log_error(f"Redis Error in validate_jwt: {str(e)}")
            frappe.local.response["http_status_code"] = 500
            frappe.local.response["message"] = _("Failed to validate token")
            return

        try:
            # Décoder le token JWT
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            # Vérifier si l'utilisateur existe
            user = payload.get("user")
            if not frappe.db.exists("User", user):
                frappe.local.response["http_status_code"] = 401
                frappe.local.response["message"] = _("Invalid User")
                return

            # Définir l'utilisateur courant
            frappe.set_user(user)
            frappe.local.login_manager = frappe.auth.LoginManager()
            frappe.local.login_manager.user = user

            # Appeler la fonction originale
            return func(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Token has expired")
            return
        except jwt.InvalidTokenError:
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Invalid Token")
            return
        except Exception as e:
            frappe.log_error(f"JWT Validation Error: {str(e)}")
            frappe.local.response["http_status_code"] = 500
            frappe.local.response["message"] = _("Internal Server Error")
            return

    return wrapper
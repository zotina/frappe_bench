import frappe
import jwt
import redis
from frappe import _
from frappe.auth import LoginManager
from datetime import datetime, timedelta


JWT_SECRET = frappe.conf.get("jwt_secret")
JWT_ALGORITHM = frappe.conf.get("jwt_algorithm") 
JWT_EXPIRY = frappe.conf.get("jwt_expiry")


REDIS_CLIENT = redis.Redis.from_url(frappe.conf.get("redis_cache"))
BLACKLIST_KEY_PREFIX = "jwt_blacklist:"

@frappe.whitelist(allow_guest=True)
def login(usr: str, pwd: str):
    """
    REST API endpoint to authenticate a user and return a JWT token.
    POST http://erpnext.localhost:8000/api/method/erpnext.controllers.api.auth_api_controller.login
    Body: {"usr": "user@example.com", "pwd": "password"}
    Returns: JWT token and user details on success, error message on failure.
    """
    try:
        # Initialiser LoginManager
        login_manager = LoginManager()

        # Authentifier l'utilisateur
        login_manager.authenticate(user=usr, pwd=pwd)

        # Vérifier si l'utilisateur doit réinitialiser son mot de passe
        if login_manager.force_user_to_reset_password():
            frappe.local.response["http_status_code"] = 403
            frappe.local.response["message"] = "Password Reset Required"
            return

        # Générer le payload JWT
        payload = {
            "user": usr,
            "exp": datetime.utcnow() + timedelta(seconds=JWT_EXPIRY),
            "iat": datetime.utcnow(),
            "sid": frappe.session.sid
        }

        # Générer le token JWT
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Exécuter les étapes post-login
        login_manager.post_login()
        
        frappe.local.response["data"] = {
            "access_token": token,
            "sid": frappe.session.sid
        }
        return

    except frappe.AuthenticationError as e:
        frappe.local.response["http_status_code"] = 401
        frappe.local.response["message"] = str(e)
        return
    except Exception as e:
        frappe.log_error(f"Login API Error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        frappe.local.response["message"] = _("Internal Server Error")
        return

@frappe.whitelist()
def logout():
    """
    REST API endpoint to log out a user and blacklist their JWT token in Redis.
    POST http://erpnext.localhost:8000/api/method/erpnext.controllers.api.auth_api_controller.logout
    Header: Authorization: Bearer <jwt_token>
    Returns: Success message on logout, error message on failure.
    """
    try:
        # Vérifier l'en-tête Authorization
        auth_header = frappe.request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Invalid or missing Authorization Header")
            return

        # Extraire le token
        token = auth_header.split(" ")[1]

        # Décoder le token pour récupérer les informations
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user = payload.get("user")
            exp = payload.get("exp")
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            frappe.local.response["http_status_code"] = 401
            frappe.local.response["message"] = _("Invalid or expired token")
            return

        # Calculer le temps restant jusqu'à l'expiration
        expiry_time = max(0, exp - int(datetime.utcnow().timestamp()))

        # Ajouter le token à la liste noire dans Redis
        redis_key = f"{BLACKLIST_KEY_PREFIX}{token}"
        REDIS_CLIENT.setex(redis_key, expiry_time, user)

        # Déconnecter la session Frappe
        frappe.local.login_manager = LoginManager()
        frappe.local.login_manager.logout()

        # Retourner un message de succès
        frappe.local.response["message"] = _("Successfully logged out")
        return

    except redis.RedisError as e:
        frappe.log_error(f"Redis Error in Logout: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        frappe.local.response["message"] = _("Failed to blacklist token")
        return
    except Exception as e:
        frappe.log_error(f"Logout API Error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        frappe.local.response["message"] = _("Internal Server Error")
        return
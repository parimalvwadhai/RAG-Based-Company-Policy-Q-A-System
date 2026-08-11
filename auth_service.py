import os
import json
import hashlib

try:
    import streamlit as st
except ImportError:
    st = None

class LocalAuthService:
    def __init__(self, filepath="config/users.json"):
        self.filepath = filepath
        self.admin_email = self._load_secret("admin_email")
        self.admin_password = self._load_secret("admin_password")
        self.invite_code = self._load_secret("invite_code")
        self.corporate_domain = self._load_secret("corporate_domain", default="@cdac.in")

        # Ensure the config directory exists
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        # Initialize JSON database file if it doesn't exist yet
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump({}, f)

    def _hash_password(self, password):
        """SHA-256 hashing to satisfy REQ-07 Security Standards."""
        return hashlib.sha256(password.encode()).hexdigest()

    def _load_secret(self, key, default=None):
        if st is not None and hasattr(st, "secrets") and "admin" in st.secrets:
            return st.secrets["admin"].get(key, default)
        return os.getenv(f"AUTH_{key.upper()}", default)

    def sign_in_user(self, email, password):
        # 1. Check configured Super-Admin first (Emergency Access)
        if self.admin_email and self.admin_password:
            if email == self.admin_email and password == self.admin_password:
                return {"success": True, "user_info": {"email": email, "role": "admin"}}
        
        # 2. Check Local Offline JSON Database
        try:
            with open(self.filepath, "r") as f:
                users = json.load(f)
            
            hashed_pass = self._hash_password(password)
            if email in users and users[email]["password"] == hashed_pass:
                return {"success": True, "user_info": {"email": email, "role": users[email]["role"]}}
            
            return {"success": False, "error": "Invalid email or password."}
        except Exception as e:
            return {"success": False, "error": f"Local Directory Error: {str(e)}"}

    def sign_up_user(self, email, password, invite_code):
        # Enforce strict invitation validation using configured secret
        if self.invite_code and invite_code != self.invite_code:
            return {"success": False, "error": "Invalid Corporate Invitation Passcode. Registration denied."}

        # Enforce corporate domain segregation (REQ-07)
        if self.corporate_domain and not email.endswith(self.corporate_domain):
            return {"success": False, "error": f"Only CDAC corporate domains ({self.corporate_domain}) are permitted."}
        
        try:
            with open(self.filepath, "r") as f:
                users = json.load(f)
            
            if email in users or (self.admin_email and email == self.admin_email):
                return {"success": False, "error": "This email address is already registered."}
            
            # Secure password hashing
            users[email] = {
                "password": self._hash_password(password),
                "role": "user"
            }
            
            with open(self.filepath, "w") as f:
                json.dump(users, f, indent=4)
                
            return {"success": True, "msg": "User successfully registered in local database!"}
        except Exception as e:
            return {"success": False, "error": f"Failed to write to database: {str(e)}"}
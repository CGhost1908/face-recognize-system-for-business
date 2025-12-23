#!/usr/bin/env python3
"""
Script to create the first admin user for the system.
Run this once to set up your admin account.
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime
import getpass

DB_PATH = "database.db"

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + pwd_hash.hex()

def create_admin():
    """Create a new admin user"""
    print("=" * 50)
    print("Admin Kullanıcısı Oluştur")
    print("=" * 50)
    
    # Get user input
    username = input("\nKullanıcı adı: ").strip()
    if not username:
        print("❌ Kullanıcı adı boş olamaz!")
        return False
    
    if len(username) < 3:
        print("❌ Kullanıcı adı en az 3 karakter olmalıdır!")
        return False
    
    email = input("E-posta adresi: ").strip()
    if not email or '@' not in email:
        print("❌ Geçerli bir e-posta adresi girin!")
        return False
    
    password = getpass.getpass("Şifre (en az 6 karakter): ")
    if len(password) < 6:
        print("❌ Şifre en az 6 karakter olmalıdır!")
        return False
    
    password_confirm = getpass.getpass("Şifre (tekrar): ")
    if password != password_confirm:
        print("❌ Şifreler eşleşmiyor!")
        return False
    
    # Hash password
    password_hash = hash_password(password)
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if user exists
        existing = cursor.execute("SELECT id FROM admin_users WHERE username=? OR email=?", (username, email)).fetchone()
        if existing:
            print("❌ Bu kullanıcı adı veya e-posta zaten kayıtlı!")
            conn.close()
            return False
        
        # Insert new admin
        cursor.execute(
            "INSERT INTO admin_users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        
        admin_id = cursor.lastrowid
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ Admin kullanıcısı başarıyla oluşturuldu!")
        print("=" * 50)
        print(f"Kullanıcı Adı: {username}")
        print(f"E-posta: {email}")
        print(f"Admin ID: {admin_id}")
        print("=" * 50)
        print("\nArtık /admin sayfasında giriş yapabilirsiniz.\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        return False

def list_admins():
    """List all admin users"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, username, email, created_at, last_login FROM admin_users WHERE is_active=1")
        admins = cursor.fetchall()
        conn.close()
        
        if not admins:
            print("Hiç admin kullanıcısı bulunamadı.")
            return
        
        print("\nAktif Admin Kullanıcıları:")
        print("-" * 80)
        for admin in admins:
            print(f"ID: {admin[0]}, Kullanıcı: {admin[1]}, E-posta: {admin[2]}")
            print(f"  Oluşturulma: {admin[3]}, Son Giriş: {admin[4]}")
        print("-" * 80)
        
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            list_admins()
        else:
            print("Kullanım: python create_admin.py [--list]")
    else:
        create_admin()

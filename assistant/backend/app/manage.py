"""Local operator commands; admin promotion is never exposed to public registration."""
import argparse
import getpass
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import Base, engine
from app.core.security import hash_password
from app.models import User, UserRole
from app.services.site_import import sync_site


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    admin = sub.add_parser('admin')
    admin.add_argument('--email', required=True)
    admin.add_argument('--name', default='مدیر سامانه')
    sync = sub.add_parser('sync-site')
    sync.add_argument('--path', required=True)
    sync.add_argument('--owner-email', required=True)
    sync.add_argument('--base-url', default='https://cesa-uh.github.io')
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        email = (args.email if args.command == 'admin' else args.owner_email).lower().strip()
        user = db.scalar(select(User).where(User.email == email))
        if args.command == 'admin':
            if not user:
                password = getpass.getpass('رمز حساب ادمین (حداقل ۱۲ کاراکتر): ')
                if len(password) < 12 or len(password) > 128:
                    parser.error('رمز باید بین ۱۲ تا ۱۲۸ کاراکتر باشد')
                if password != getpass.getpass('تکرار رمز: '):
                    parser.error('تکرار رمز برابر نیست')
                user = User(email=email, first_name=args.name, last_name='', password_hash=hash_password(password), role=UserRole.ADMIN)
                db.add(user)
            else:
                user.role = UserRole.ADMIN
            db.commit()
            print('حساب ادمین آماده است؛ رمز حساب موجود تغییر نکرد.')
        else:
            if not user or user.role not in {UserRole.ADMIN, UserRole.TEACHER}:
                parser.error('حساب مالک باید قبلاً به عنوان استاد یا ادمین ساخته شده باشد')
            print(json.dumps(sync_site(db, args.path, user, args.base_url), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

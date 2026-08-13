import time

from passlib.context import CryptContext

class PasswordManager:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, plain_password: str) -> str:
        return self.pwd_context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str):
        return self.pwd_context.verify(plain_password, hashed_password)

pwd_manager = PasswordManager()

if __name__ == "__main__":
    plain_password = "123456"
    start = time.time()
    for i in range(1):
        hashed_password = pwd_manager.hash_password(plain_password)
        print(hashed_password)
        is_true = pwd_manager.verify_password(plain_password, hashed_password)
        print(is_true)
    end = time.time()
    print(f"耗时：{end - start}s")


import bcrypt
import sys

# Check bcrypt version
print(f"Bcrypt version: {getattr(bcrypt, '__version__', 'unknown')}")

# Try the monkeypatch
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (object,), {"__version__": bcrypt.__version__})
    print("Applied monkeypatch")

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    test_pass = "123123"
    print(f"Testing with password: {test_pass}")
    
    hashed = pwd_context.hash(test_pass)
    print(f"Hashed successfully: {hashed}")
    
    matches = pwd_context.verify(test_pass, hashed)
    print(f"Verified successfully: {matches}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

"""
test_e2e.py
End-to-end diagnostic: Login -> Upload -> Process -> Chat about doc -> Verify response.
Usage: python test_e2e.py (with Flask server running on port 5000)
"""

import time, requests, json, sys, os, uuid

BASE_URL      = "http://127.0.0.1:5000"
TEST_EMAIL    = "shivcoretech11@gmail.com"
TEST_PASSWORD = "Admin.123"

TESTS_PASSED, TESTS_FAILED = 0, 0

def ok(msg):
    global TESTS_PASSED; TESTS_PASSED += 1
    print(f"  PASS: {msg}")

def fail(msg):
    global TESTS_FAILED; TESTS_FAILED += 1
    print(f"  FAIL: {msg}")

S = requests.Session()

def test_login():
    print("\n[1] LOGIN")
    try:
        r = S.post(f"{BASE_URL}/mobile/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=10)
        d = r.json()
        if d.get("success"):
            ok(f"Logged in: {d['user']['name']} id={d['user']['id']}")
            return d["user"]["id"]
        fail(f"Login failed: {d.get('message')}")
    except Exception as e:
        fail(f"Login exception: {e}")
    return None

def test_upload():
    print("\n[2] UPLOAD TEST DOCUMENT")
    test_pdf = "resume.pdf"
    if not os.path.exists(test_pdf):
        fail(f"Could not find {test_pdf}")
        return None
    try:
        with open(test_pdf, "rb") as f:
            r = S.post(f"{BASE_URL}/mobile/documents/upload",
                       files={"file": (test_pdf, f)}, timeout=30)
        d = r.json()
        if d.get("success"):
            doc = d["document"]
            ok(f"Uploaded: {doc['original_name']} id={doc['id']} status={doc['status']}")
            return doc["id"]
        fail(f"Upload failed: {d}")
    except Exception as e:
        fail(f"Upload exception: {e}")
    return None

def test_wait_ready(doc_id, timeout=60):
    print(f"\n[3] WAIT FOR PROCESSING doc_id={doc_id}")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = S.get(f"{BASE_URL}/mobile/documents/{doc_id}/status", timeout=10)
            d = r.json()
            st = d.get("status", "?")
            print(f"    status: {st}")
            if st == "ready":
                ok(f"Document ready pages={d.get('page_count','?')}")
                return True
            if st.startswith("Failed"):
                fail(f"Processing failed: {st}")
                return False
            time.sleep(5)
        except Exception as e:
            fail(f"Status poll: {e}"); return False
    fail(f"Timeout {timeout}s")
    return False

def test_chat(label, question, session_uuid=None):
    if not session_uuid:
        session_uuid = str(uuid.uuid4())
    try:
        r = S.post(f"{BASE_URL}/mobile/chat", json={"message": question, "session_uuid": session_uuid}, timeout=30)
        d = r.json()
        reply = d.get("reply", "")
        if d.get("success") and reply and len(reply) > 5:
            ok(f"{label}: {reply[:80]}")
            print(f"    intent={d.get('intent')} source={d.get('source_used','?')}")
            return True
        fail(f"{label}: success={d.get('success')} reply='{reply[:80]}'")
        print(f"    Full response: {json.dumps(d)[:300]}")
    except Exception as e:
        fail(f"{label} exception: {e}")
    return False

if __name__ == "__main__":
    print("=" * 60)
    print("Renvora AI End-to-End Diagnostic Test")
    print(f"Server: {BASE_URL}")
    print("=" * 60)

    user_id = test_login()
    if not user_id:
        print("Cannot continue: login failed. Is Flask running?")
        sys.exit(1)

    print("\n[GENERAL KNOWLEDGE TESTS]")
    test_chat("Hello", "Hello, how are you?")
    test_chat("Math", "What is 2 + 2?")
    test_chat("Python", "What is Python programming language?")

    doc_id = test_upload()
    if doc_id and test_wait_ready(doc_id):
        print("\n[DOCUMENT CHAT TESTS]")
        sess = str(uuid.uuid4())
        test_chat("Doc summary", "Summarize the uploaded document", sess)
        test_chat("Doc question", "What is Sarthak's education or experience according to the document?", sess)

    total = TESTS_PASSED + TESTS_FAILED
    print(f"\n{'='*60}")
    print(f"RESULTS: {TESTS_PASSED}/{total} passed, {TESTS_FAILED} failed")
    if TESTS_FAILED == 0:
        print("ALL TESTS PASSED - End-to-end flow working!")
    else:
        print(f"{TESTS_FAILED} FAILED - See output above.")
    sys.exit(0 if TESTS_FAILED == 0 else 1)

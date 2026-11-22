"""Live end-to-end smoke test against a running SkillVar server (real HTTP, cookies, CSRF, multipart upload).
Standard library only. Usage:  python scripts/smoke_test.py http://127.0.0.1:8000 [--user NAME]"""
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar

BASE = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "http://127.0.0.1:8000").rstrip("/")
USER = sys.argv[sys.argv.index("--user") + 1] if "--user" in sys.argv else "smoke_user"
PW = "a-long-strong-pass-9"
jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
failures = []


def request(req):
    try:
        r = opener.open(req)
        return r.status, r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.url


def get(path):
    return request(urllib.request.Request(BASE + path))


def token():
    return next((c.value for c in jar if c.name == "csrftoken"), "")


def post(path, data):
    if not token():
        get("/accounts/login/")
    body = urllib.parse.urlencode({**data, "csrfmiddlewaretoken": token()}, doseq=True).encode()
    return request(urllib.request.Request(BASE + path, body, headers={"Referer": BASE + path}))


def upload(path, filename, content):
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="csrfmiddlewaretoken"\r\n\r\n{token()}\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'.encode(),
             content, f"\r\n--{boundary}--\r\n".encode()]
    req = urllib.request.Request(BASE + path, b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Referer": BASE + path})
    return request(req)


def pdf(lines):
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    content = "BT /F1 11 Tf 40 780 Td 13 TL " + " ".join(f"({esc(ln)}) Tj T*" for ln in lines) + " ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode(), b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n" + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(name)


RESUME = ["Jane Doe", "jane@example.com | +1 555 123 4567 | github.com/jane", "Skills", "Python, SQL, Git", "Experience",
          "Built ETL pipelines in Python and Airflow that reduced load time by 40%.", "Improved query performance on PostgreSQL by 60%.",
          "Projects", "Finance tracker built with Django and Docker.", "Education", "B.Sc. in Computer Science"]
JOB = "Job Title: Junior Data Engineer\nRequirements:\n- 2+ years of experience\n- Python and SQL\n- Experience with Airflow\nNice to have:\n- Docker\n"

s, html, _ = get("/")
check("homepage 200 + branding", s == 200 and "Prove Your Potential" in html)
check("static CSS served", get("/static/css/app.css")[0] == 200 and get("/static/vendor/bootstrap.min.css")[0] == 200)
check("health check reports postgresql", '"postgresql"' in get("/healthz/")[1])
check("anonymous dashboard redirects to login", "/accounts/login/" in get("/dashboard/")[2])
get("/accounts/register/")
s, html, url = post("/accounts/register/", {"username": USER, "email": f"{USER}@example.com", "password1": PW, "password2": PW})
check("register -> onboarding", url.endswith("/accounts/onboarding/"), url)
goal = re.search(r'<option value="(\d+)"[^>]*>Junior Data Engineer', html)
s, html, url = post("/accounts/onboarding/", {"career_goal": goal.group(1), "education_level": "bachelor", "experience_level": "entry", "years_experience": "1", "preferred_location": "Remote"})
check("profile saved -> self-assessment", url.endswith("/onboarding/skills/") and "not verified skills" in html.lower(), url)
s, html, url = post("/accounts/onboarding/skills/", {"skill_sql": "0.85", "skill_python": "0.6"})
check("self-assessment saved -> dashboard", url.endswith("/dashboard/") and "Recommended next action" in html, url)
s, html, url = upload("/resumes/upload/", "cv.pdf", pdf(RESUME))
check("resume uploaded and analyzed", "/resumes/" in url and "Detected skills" in html and "Airflow" in html, url)
check("resume provenance shown", "reduced load time" in html)
rid = re.search(r"/resumes/(\d+)/", url).group(1)
check("resume download works for the owner", get(f"/resumes/{rid}/download/")[1].startswith("%PDF"))
check("raw file is not reachable by any public path", get("/media/resumes/1/x.pdf")[0] == 404)
s, html, url = post("/jobs/analyze/", {"text": JOB})
check("job analyzed (required/preferred)", "Required skills" in html and "Preferred skills" in html and "Docker" in html, url)
jid = re.search(r"/jobs/(\d+)/", url).group(1)
s, html, url = post(f"/jobs/{jid}/match/", {})
check("match calculated with explanation", "How the score was calculated" in html and "not the probability of being hired" in html, url)
s, html, _ = get("/assessments/python-fundamentals/")
qid = re.search(r'name="q(\d+)"', html).group(1)
s, html, url = post("/assessments/python-fundamentals/", {f"q{qid}": "2"})
check("MCQ graded on the server", "/assessments/attempts/" in url and "100%" in html, url)
s, html, _ = get("/assessments/sql-practice/")
qid = re.search(r'<textarea[^>]*name="q(\d+)"', html).group(1)
s, html, url = post("/assessments/sql-practice/", {f"q{qid}": "SELECT name FROM customers WHERE country='IN' ORDER BY name"})
check("SQL executed in sandbox and graded", "/assessments/attempts/" in url and "100%" in html, url)
s, html, _ = post("/assessments/sql-practice/", {f"q{qid}": "DROP TABLE customers"})
check("destructive SQL scores zero", "could not run" in html)
s, html, _ = get("/readiness/")
check("readiness page", "Expected readiness" in html and "Conservative readiness" in html)
s, html, url = post("/roadmap/generate/", {})
check("roadmap generated", "Practice task" in html and "You are done when" in html)
item = re.search(r"/roadmap/items/(\d+)/", html).group(1)
s, html, _ = post(f"/roadmap/items/{item}/", {"action": "complete", "note": "done in smoke test"})
check("roadmap item completed", "Marked" in html or "Done" in html)
s, html, _ = get("/dashboard/")
check("dashboard shows real data", "Roadmap progress" in html and "Recent assessments" in html and "Readiness (expected)" in html)
s, html, _ = get("/api/v1/me/skills/")
check("API returns my skills", '"slug": "python"' in html or '"slug":"python"' in html)
check("logout then dashboard blocked", post("/accounts/logout/", {})[0] == 200 and "/accounts/login/" in get("/dashboard/")[2])
s, html, url = post("/accounts/login/", {"username": f"{USER}@example.com", "password": PW})
check("login with email works", url.endswith("/dashboard/"), url)
s, html, _ = get("/assessments/history/")
check("history persisted across sessions", "Python fundamentals" in html and "SQL practice" in html)
print("\nRESULT:", "ALL PASSED" if not failures else f"{len(failures)} FAILED: {failures}")
sys.exit(1 if failures else 0)

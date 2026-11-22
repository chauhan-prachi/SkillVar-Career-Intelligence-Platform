import io

import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("createcachetable", verbosity=0)   # the DB-backed cache table used by rate limits


@pytest.fixture(autouse=True)
def _private_media(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"      # uploads never touch the real folder during tests
    import apps.resumes.models as m
    from apps.resumes.storage import PrivateStorage
    m.Resume._meta.get_field("file").storage = PrivateStorage()


@pytest.fixture
def seeded(db):
    call_command("seed_data", verbosity=0)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user("ana", email="ana@example.com", password="a-long-strong-pass-9")


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user("bob", email="bob@example.com", password="a-long-strong-pass-9")


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def goal_user(seeded, user):
    from apps.skills.models import Role
    user.profile.career_goal = Role.objects.get(slug="junior-data-engineer")
    user.profile.save()
    return user


@pytest.fixture
def goal_client(client, goal_user):
    client.force_login(goal_user)
    return client


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[str]) -> bytes:
    """A tiny but valid single-page text PDF (so extraction can be tested without extra libraries)."""
    content = "BT /F1 11 Tf 40 780 Td 13 TL " + " ".join(f"({_esc(ln)}) Tj T*" for ln in lines) + " ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n" + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


def make_docx(paragraphs: list[str]) -> bytes:
    import docx
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


SAMPLE_RESUME = [
    "Jane Doe", "jane@example.com | +1 555 123 4567 | github.com/jane",
    "Summary", "Data engineer with 3 years of experience building pipelines.",
    "Skills", "Python, SQL, Git",
    "Experience", "Data Engineer, Acme 2022-2025",
    "Built ETL pipelines in Python and Airflow that reduced load time by 40%.",
    "Improved query performance on PostgreSQL by 60%.",
    "Projects", "Personal finance tracker built with Django and Docker.", "Deployed a REST API using FastAPI.",
    "Education", "B.Sc. in Computer Science, State University",
]

"""Small read-only JSON API (session authentication). Every endpoint is scoped to the signed-in user."""
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.profile import build_signals
from apps.matching import services
from apps.matching.models import JobMatch
from apps.matching.scoring import LABELS, skill_credit
from apps.skills.models import Skill


class SkillListView(APIView):
    def get(self, request):
        qs = Skill.objects.filter(is_active=True).select_related("category").prefetch_related("aliases")
        return Response([{"slug": s.slug, "name": s.name, "category": s.category.name,
                          "aliases": [a.alias for a in s.aliases.all()]} for s in qs])


class MySkillsView(APIView):
    def get(self, request):
        signals, _ = build_signals(request.user)
        out = []
        for skill in Skill.objects.order_by("name"):
            sig = signals.get(skill.slug)
            if sig and (sig.claimed is not None or sig.resume or sig.assessed):
                status, code, exp, cons = skill_credit(sig, settings.MATCH_CREDITS, settings.UNDECIDED_ASSESSMENT_CAP)
                out.append({"slug": skill.slug, "name": skill.name, "status": status, "evidence": LABELS[code],
                            "credit": round(exp, 3), "conservative_credit": round(cons, 3), "assessments": sig.n_assessments})
        return Response(out)


class MyReadinessView(APIView):
    def get(self, request):
        role = request.user.profile.career_goal
        if role is None:
            return Response({"detail": "Choose a career goal first."}, status=409)
        return Response({"role": role.slug, "formula_version": settings.FORMULA_VERSION, **services.readiness(request.user, role).to_dict()})


class MyMatchesView(APIView):
    def get(self, request):
        qs = JobMatch.objects.filter(user=request.user).select_related("job")[:50]
        return Response([{"id": m.id, "job": m.job.title, "score": m.score, "created_at": m.created_at} for m in qs])

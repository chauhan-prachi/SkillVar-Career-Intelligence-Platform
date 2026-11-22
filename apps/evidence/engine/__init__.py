"""Pure-Python skill-intelligence engine (no Django imports): prerequisite graph, Beta beliefs, recommender.
Ported from the earlier VerityRole AI project together with its tests."""
from .graph import SkillGraph
from .model import LearnerProfile, SkillState
from .recommender import Action, recommend_next
from .types import RoleSpec

__all__ = ["SkillGraph", "LearnerProfile", "SkillState", "Action", "recommend_next", "RoleSpec"]

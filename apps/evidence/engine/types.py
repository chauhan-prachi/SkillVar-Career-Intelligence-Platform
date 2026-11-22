from dataclasses import dataclass


@dataclass
class RoleSpec:
    title: str
    requirements: dict[str, float]   # skill slug -> importance

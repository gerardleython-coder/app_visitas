from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RankingPeriod(StrEnum):
    SEMANA = "SEMANA"
    MES = "MES"


@dataclass(frozen=True, slots=True)
class LeaderRankingEntry:
    leader_id: UUID
    leader_name: str
    completed_visits: int
    position: int
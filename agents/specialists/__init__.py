# Specialist Agents Module
# Background agents for scholarship discovery, appeal strategy, and deadline management

from agents.specialists.scholarship_scout import ScholarshipScoutAgent
from agents.specialists.appeal_strategist import AppealStrategistAgent
from agents.specialists.deadline_sentinel import DeadlineSentinelAgent
from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AResponse

__all__ = [
    'ScholarshipScoutAgent',
    'AppealStrategistAgent',
    'DeadlineSentinelAgent',
    'A2AProtocol',
    'A2ARequest',
    'A2AResponse',
]

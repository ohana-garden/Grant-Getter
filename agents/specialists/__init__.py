# Specialist Agents Module
# Background agents for scholarship discovery, appeal strategy, deadline management, and document analysis

from agents.specialists.scholarship_scout import ScholarshipScoutAgent
from agents.specialists.appeal_strategist import AppealStrategistAgent
from agents.specialists.deadline_sentinel import DeadlineSentinelAgent
from agents.specialists.document_analyst import DocumentAnalystAgent
from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AResponse

__all__ = [
    'ScholarshipScoutAgent',
    'AppealStrategistAgent',
    'DeadlineSentinelAgent',
    'DocumentAnalystAgent',
    'A2AProtocol',
    'A2ARequest',
    'A2AResponse',
]

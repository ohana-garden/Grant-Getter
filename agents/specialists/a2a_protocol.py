"""A2A Protocol - Agent-to-Agent Communication

Implements the protocol for agents to communicate with each other.
Used by Ambassador to query specialist agents.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class A2AAction(Enum):
    """Available A2A actions."""
    # Scholarship Scout actions
    SEARCH_SCHOLARSHIPS = "search_scholarships"
    GET_MATCHES = "get_matches"
    VERIFY_SCHOLARSHIP = "verify_scholarship"
    GET_SCOUT_STATS = "get_scout_stats"

    # Appeal Strategist actions
    ANALYZE_SCHOOL = "analyze_school"
    GET_STRATEGIES = "get_strategies"
    DRAFT_APPEAL = "draft_appeal"
    GET_SUCCESS_PATTERNS = "get_success_patterns"

    # Deadline Sentinel actions (future)
    GET_DEADLINES = "get_deadlines"
    SCRAPE_DEADLINE = "scrape_deadline"

    # Generic
    HEALTH_CHECK = "health_check"


class A2AStatus(Enum):
    """Status of an A2A request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class A2ARequest:
    """A request from one agent to another."""
    id: str
    source_agent: str
    target_agent: str
    action: A2AAction
    params: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    timeout_seconds: int = 30

    @classmethod
    def create(
        cls,
        source: str,
        target: str,
        action: A2AAction,
        params: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
    ) -> 'A2ARequest':
        """Create a new A2A request.

        Args:
            source: Source agent name
            target: Target agent name
            action: Action to perform
            params: Action parameters
            context: Additional context

        Returns:
            A2ARequest object
        """
        return cls(
            id=str(uuid.uuid4()),
            source_agent=source,
            target_agent=target,
            action=action,
            params=params or {},
            context=context or {},
        )


@dataclass
class A2AResponse:
    """A response from a specialist agent."""
    request_id: str
    status: A2AStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    responded_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def success(
        cls,
        request_id: str,
        data: Dict[str, Any],
        processing_time_ms: float = 0.0,
    ) -> 'A2AResponse':
        """Create a success response.

        Args:
            request_id: Original request ID
            data: Response data
            processing_time_ms: Processing time

        Returns:
            A2AResponse object
        """
        return cls(
            request_id=request_id,
            status=A2AStatus.COMPLETED,
            data=data,
            processing_time_ms=processing_time_ms,
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        error: str,
    ) -> 'A2AResponse':
        """Create a failure response.

        Args:
            request_id: Original request ID
            error: Error message

        Returns:
            A2AResponse object
        """
        return cls(
            request_id=request_id,
            status=A2AStatus.FAILED,
            error=error,
        )


class A2AProtocol:
    """Protocol handler for agent-to-agent communication.

    Manages routing requests between agents and tracking request history.
    """

    def __init__(self):
        """Initialize A2A protocol handler."""
        self._agents: Dict[str, Any] = {}
        self._request_history: List[A2ARequest] = []
        self._response_history: List[A2AResponse] = []

    def register_agent(self, name: str, agent: Any):
        """Register an agent with the protocol.

        Args:
            name: Agent name
            agent: Agent instance
        """
        self._agents[name] = agent
        logger.info(f"Registered agent: {name}")

    def unregister_agent(self, name: str):
        """Unregister an agent.

        Args:
            name: Agent name
        """
        self._agents.pop(name, None)
        logger.info(f"Unregistered agent: {name}")

    async def send_request(
        self,
        request: A2ARequest,
    ) -> A2AResponse:
        """Send a request to a target agent.

        Args:
            request: A2ARequest to send

        Returns:
            A2AResponse from target agent
        """
        start_time = datetime.utcnow()
        self._request_history.append(request)

        # Check if target agent is registered
        if request.target_agent not in self._agents:
            response = A2AResponse.failure(
                request.id,
                f"Agent '{request.target_agent}' not registered"
            )
            self._response_history.append(response)
            return response

        agent = self._agents[request.target_agent]

        try:
            # Route to appropriate handler
            data = await self._route_request(agent, request)

            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds() * 1000

            response = A2AResponse.success(
                request.id,
                data,
                processing_time,
            )

        except Exception as e:
            logger.error(f"A2A request failed: {e}")
            response = A2AResponse.failure(request.id, str(e))

        self._response_history.append(response)
        return response

    async def _route_request(
        self,
        agent: Any,
        request: A2ARequest,
    ) -> Dict[str, Any]:
        """Route a request to the appropriate agent handler.

        Args:
            agent: Target agent
            request: Request to route

        Returns:
            Response data dict
        """
        action = request.action
        params = request.params

        # Scholarship Scout actions
        if action == A2AAction.SEARCH_SCHOLARSHIPS:
            results = await agent.query_scholarships(
                query=params.get('query', ''),
                profile_id=params.get('profile_id'),
                limit=params.get('limit', 10),
            )
            return {
                'scholarships': [
                    {
                        'id': s.id,
                        'name': s.name,
                        'amount_max': s.amount_max,
                        'deadline': s.deadline.isoformat() if s.deadline else None,
                        'legitimacy': s.legitimacy.value,
                    }
                    for s in results
                ]
            }

        elif action == A2AAction.GET_MATCHES:
            matches = await agent.get_matches_for_profile(
                profile_id=params.get('profile_id', ''),
            )
            return {
                'matches': [
                    {
                        'scholarship_id': m.scholarship_id,
                        'match_score': m.match_score,
                        'reasons': m.match_reasons,
                    }
                    for m in matches
                ]
            }

        elif action == A2AAction.VERIFY_SCHOLARSHIP:
            result = await agent.verify_scholarship(
                scholarship_id=params.get('scholarship_id', ''),
            )
            return result

        elif action == A2AAction.GET_SCOUT_STATS:
            return agent.get_stats()

        # Appeal Strategist actions
        elif action == A2AAction.ANALYZE_SCHOOL:
            result = await agent.analyze_school(
                school_id=params.get('school_id', ''),
            )
            return result

        elif action == A2AAction.GET_STRATEGIES:
            strategies = await agent.get_strategies(
                school_id=params.get('school_id', ''),
                context=params.get('context', {}),
            )
            return {'strategies': strategies}

        elif action == A2AAction.DRAFT_APPEAL:
            draft = await agent.draft_appeal(
                school_id=params.get('school_id', ''),
                student_context=params.get('student_context', {}),
                strategy_id=params.get('strategy_id'),
            )
            return {'draft': draft}

        elif action == A2AAction.GET_SUCCESS_PATTERNS:
            patterns = await agent.get_success_patterns(
                school_id=params.get('school_id'),
            )
            return {'patterns': patterns}

        # Generic actions
        elif action == A2AAction.HEALTH_CHECK:
            return {
                'status': 'healthy',
                'agent': request.target_agent,
                'timestamp': datetime.utcnow().isoformat(),
            }

        else:
            raise ValueError(f"Unknown action: {action}")

    def get_registered_agents(self) -> List[str]:
        """Get list of registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def get_request_history(
        self,
        limit: int = 100,
    ) -> List[A2ARequest]:
        """Get recent request history.

        Args:
            limit: Maximum entries to return

        Returns:
            List of recent requests
        """
        return self._request_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get protocol statistics.

        Returns:
            Stats dict
        """
        total_requests = len(self._request_history)
        total_responses = len(self._response_history)

        successful = sum(
            1 for r in self._response_history
            if r.status == A2AStatus.COMPLETED
        )
        failed = sum(
            1 for r in self._response_history
            if r.status == A2AStatus.FAILED
        )

        avg_time = 0.0
        if self._response_history:
            times = [r.processing_time_ms for r in self._response_history if r.processing_time_ms > 0]
            if times:
                avg_time = sum(times) / len(times)

        return {
            'registered_agents': len(self._agents),
            'agent_names': list(self._agents.keys()),
            'total_requests': total_requests,
            'successful_requests': successful,
            'failed_requests': failed,
            'success_rate': successful / total_requests if total_requests > 0 else 0,
            'average_processing_time_ms': round(avg_time, 2),
        }


# Convenience functions for creating requests
def create_scholarship_search_request(
    source: str,
    query: str,
    profile_id: Optional[str] = None,
    limit: int = 10,
) -> A2ARequest:
    """Create a scholarship search request.

    Args:
        source: Source agent name
        query: Search query
        profile_id: Optional profile ID
        limit: Max results

    Returns:
        A2ARequest
    """
    return A2ARequest.create(
        source=source,
        target="scholarship_scout",
        action=A2AAction.SEARCH_SCHOLARSHIPS,
        params={
            'query': query,
            'profile_id': profile_id,
            'limit': limit,
        },
    )


def create_verify_scholarship_request(
    source: str,
    scholarship_id: str,
) -> A2ARequest:
    """Create a scholarship verification request.

    Args:
        source: Source agent name
        scholarship_id: Scholarship to verify

    Returns:
        A2ARequest
    """
    return A2ARequest.create(
        source=source,
        target="scholarship_scout",
        action=A2AAction.VERIFY_SCHOLARSHIP,
        params={'scholarship_id': scholarship_id},
    )


def create_draft_appeal_request(
    source: str,
    school_id: str,
    student_context: Dict[str, Any],
    strategy_id: Optional[str] = None,
) -> A2ARequest:
    """Create an appeal draft request.

    Args:
        source: Source agent name
        school_id: School to appeal to
        student_context: Anonymized student context
        strategy_id: Optional specific strategy

    Returns:
        A2ARequest
    """
    return A2ARequest.create(
        source=source,
        target="appeal_strategist",
        action=A2AAction.DRAFT_APPEAL,
        params={
            'school_id': school_id,
            'student_context': student_context,
            'strategy_id': strategy_id,
        },
    )

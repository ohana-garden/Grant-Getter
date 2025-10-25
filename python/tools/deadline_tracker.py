"""
Deadline Tracker Tool for Agent Zero

Manages grant deadlines and reminders.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import os


class DeadlineTracker:
    """
    Deadline Tracker Tool for Agent Zero
    
    Manages grant submission deadlines and notifications.
    """
    
    def __init__(self, agent=None, **kwargs):
        self.agent = agent
        self.name = "deadline_tracker"
        self.args = kwargs
        self.storage_file = kwargs.get('storage_file', '/home/claude/grant-agent/data/deadlines.json')
        
    async def execute(
        self,
        action: str,
        grant_id: Optional[str] = None,
        deadline: Optional[str] = None,
        notification_days_before: int = 7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Track grant deadlines
        
        Args:
            action: 'add', 'list', 'remove', 'upcoming'
            grant_id: Grant opportunity ID
            deadline: ISO format date (for 'add')
            notification_days_before: Days before deadline to remind
            
        Returns:
            Dict with status and deadline information
        """
        
        try:
            if action == "add":
                return await self._add_deadline(grant_id, deadline, notification_days_before)
            elif action == "list":
                return await self._list_deadlines()
            elif action == "upcoming":
                days = kwargs.get('days', 30)
                return await self._upcoming_deadlines(days)
            elif action == "remove":
                return await self._remove_deadline(grant_id)
            else:
                return {'error': f"Unknown action: {action}"}
                
        except Exception as e:
            return {
                'error': str(e),
                'message': f"Error tracking deadlines: {str(e)}"
            }
    
    async def _add_deadline(
        self,
        grant_id: str,
        deadline: str,
        notification_days: int
    ) -> Dict[str, Any]:
        """Add a deadline"""
        
        deadlines = self._load_deadlines()
        
        # Parse deadline
        deadline_dt = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        
        # Calculate notification date
        notification_date = deadline_dt - timedelta(days=notification_days)
        
        # Add to tracking
        deadlines[grant_id] = {
            'grant_id': grant_id,
            'deadline': deadline,
            'deadline_datetime': deadline_dt.isoformat(),
            'notification_date': notification_date.isoformat(),
            'notification_days_before': notification_days,
            'status': 'active',
            'added_at': datetime.now().isoformat()
        }
        
        self._save_deadlines(deadlines)
        
        days_until = (deadline_dt - datetime.now()).days
        
        return {
            'status': 'added',
            'grant_id': grant_id,
            'deadline': deadline,
            'days_until_deadline': days_until,
            'notification_date': notification_date.isoformat(),
            'message': f"Added deadline for {grant_id} ({days_until} days from now)"
        }
    
    async def _list_deadlines(self) -> Dict[str, Any]:
        """List all tracked deadlines"""
        
        deadlines = self._load_deadlines()
        
        # Sort by deadline date
        sorted_deadlines = sorted(
            deadlines.values(),
            key=lambda x: x['deadline_datetime']
        )
        
        # Add days until for each
        for dl in sorted_deadlines:
            deadline_dt = datetime.fromisoformat(dl['deadline_datetime'])
            dl['days_until'] = (deadline_dt - datetime.now()).days
        
        return {
            'deadlines': sorted_deadlines,
            'total_count': len(sorted_deadlines),
            'message': f"Tracking {len(sorted_deadlines)} deadlines"
        }
    
    async def _upcoming_deadlines(self, days: int = 30) -> Dict[str, Any]:
        """Get deadlines within specified days"""
        
        deadlines = self._load_deadlines()
        cutoff_date = datetime.now() + timedelta(days=days)
        
        upcoming = []
        for dl in deadlines.values():
            deadline_dt = datetime.fromisoformat(dl['deadline_datetime'])
            if datetime.now() <= deadline_dt <= cutoff_date:
                days_until = (deadline_dt - datetime.now()).days
                dl['days_until'] = days_until
                upcoming.append(dl)
        
        # Sort by urgency
        upcoming.sort(key=lambda x: x['days_until'])
        
        return {
            'upcoming_deadlines': upcoming,
            'count': len(upcoming),
            'within_days': days,
            'message': f"{len(upcoming)} deadlines in next {days} days"
        }
    
    async def _remove_deadline(self, grant_id: str) -> Dict[str, Any]:
        """Remove a deadline"""
        
        deadlines = self._load_deadlines()
        
        if grant_id in deadlines:
            del deadlines[grant_id]
            self._save_deadlines(deadlines)
            return {
                'status': 'removed',
                'grant_id': grant_id,
                'message': f"Removed deadline for {grant_id}"
            }
        else:
            return {
                'status': 'not_found',
                'grant_id': grant_id,
                'message': f"Deadline not found for {grant_id}"
            }
    
    def _load_deadlines(self) -> Dict[str, Any]:
        """Load deadlines from storage"""
        
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_deadlines(self, deadlines: Dict[str, Any]):
        """Save deadlines to storage"""
        
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        with open(self.storage_file, 'w') as f:
            json.dump(deadlines, f, indent=2)


# Tool metadata
tool_info = {
    'name': 'deadline_tracker',
    'description': 'Add and track grant deadlines with reminders',
    'example': 'deadline_tracker(action="add", grant_id="ED-2025-001", deadline="2025-12-31T23:59:59")'
}

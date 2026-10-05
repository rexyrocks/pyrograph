"""One-shot local workflow escalation job for a persistent SQLite demo store.

Set HEATSHIELD_WORKFLOW_DB to a database on a durable mounted volume, then
run this command on a trusted scheduler. It sends no alerts or messages.
"""
import json
import os
from pathlib import Path

from backend.municipal import SqliteMunicipalWorkflowService


if __name__ == '__main__':
    path = os.getenv('HEATSHIELD_WORKFLOW_DB')
    if not path:
        raise SystemExit('HEATSHIELD_WORKFLOW_DB is required for scheduled escalation')
    workflows = SqliteMunicipalWorkflowService(Path(path)).escalate_due()
    print(json.dumps({'escalated': [item.workflow_id for item in workflows],
                      'count': len(workflows)}))

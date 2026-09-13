"""Exercise actual production API routes locally with deterministic offline state.

No sockets or real providers. Clock advancement is a test harness action,
never a publicly available endpoint. Run: python3 -m scripts.rehearse_demo
"""
import json
import os
from datetime import datetime, UTC, timedelta

os.environ['HEATSHIELD_API_KEY'] = 'local-rehearsal-only-key-0000000000000000'
os.environ['HEATSHIELD_ALERT_PROVIDER'] = 'demo'

from fastapi.testclient import TestClient
from backend.vercel_app import app
from backend.alerts import AlertService, DemoDeliveryProvider
from backend.municipal import MunicipalWorkflowService


def rehearse():
    headers = {'X-API-Key': os.environ['HEATSHIELD_API_KEY']}
    clock = [datetime(2026, 9, 14, 9, 0, tzinfo=UTC)]
    report = {'mode': 'offline simulation', 'real_delivery_enabled': False, 'storage': 'in_memory_demo'}
    payload = {
        'idempotency_key': 'rehearsal:jaipur:sms:first',
        'deduplication_key': 'rehearsal:jaipur:event', 'channel': 'sms',
        'recipient_scope': 'municipal-role:incident-command-lead',
        'location_id': 'jaipur', 'priority_band': 'Severe',
        'message': 'Synthetic rehearsal only. No message is sent.', 'max_attempts': 2,
    }
    with TestClient(app) as client:
        app.state.municipal_service = MunicipalWorkflowService(clock=lambda: clock[0])
        def post(path, body):
            response = client.post(path, json=body, headers=headers)
            assert response.status_code == 200, (path, response.text)
            return response.json()
        first = post('/alerts/dispatch', payload)
        assert first['alert']['status'] == 'delivered'
        assert first['alert']['real_delivery_enabled'] is False
        replay = post('/alerts/dispatch', payload)
        assert replay['idempotent_replay'] is True
        duplicate = post('/alerts/dispatch', {**payload, 'idempotency_key': 'rehearsal:duplicate'})
        assert duplicate['alert']['status'] == 'suppressed'
        workflow = post('/municipal/workflows', {
            'idempotency_key': 'rehearsal:workflow', 'location_id': 'jaipur',
            'priority_band': 'Severe', 'actions': [{'priority': 'emergency', 'action': 'Demo readiness review.'}],
        })['workflow']
        workflow_id = workflow['workflow_id']
        acknowledged = post(f'/municipal/workflows/{workflow_id}/transitions', {
            'to_status': 'acknowledged', 'actor_role': 'incident-command-lead',
            'reason': 'Duty role acknowledged the synthetic exercise.',
        })
        assert acknowledged['status'] == 'acknowledged'
        clock[0] += timedelta(minutes=6)
        eligibility = client.get(f'/municipal/workflows/{workflow_id}/escalation', headers=headers).json()
        assert eligibility['eligible'] is True
        report.update(success=first, replay=replay['idempotent_replay'], duplicate=duplicate, acknowledgement=acknowledged, escalation=eligibility)
        app.state.alert_service = AlertService(DemoDeliveryProvider(outcomes=('failed',)))
        failure = post('/alerts/dispatch', {**payload, 'idempotency_key': 'rehearsal:failure'})
        assert failure['alert']['status'] == 'failed'
        assert failure['alert']['attempts'] == 2
        report['explicit_failure'] = failure
    with TestClient(app) as client:
        reset = client.get(f'/municipal/workflows/{workflow_id}', headers=headers)
        assert reset.status_code == 404
        report['restart_record_status'] = reset.status_code
    return report


if __name__ == '__main__':
    print(json.dumps(rehearse(), indent=2))

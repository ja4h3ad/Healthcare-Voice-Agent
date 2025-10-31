# app/mcp/schemas/fhir_appointment.py
"""
Convert MongoDB appointment documents to FHIR R4 Appointment resources
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta, UTC

import pytz


def mongo_status_to_fhir(mongo_status: str) -> str:
    """
    Map MongoDB appointment status to FHIR status

    FHIR statuses: proposed | pending | booked | arrived | fulfilled | cancelled | noshow | entered-in-error | checked-in | waitlist
    """
    status_map = {
        'requested': 'pending',
        'confirmed': 'booked',
        'cancelled': 'cancelled',
        'completed': 'fulfilled',
        'rescheduled': 'pending'
    }
    return status_map.get(mongo_status, 'booked')


def fhir_status_to_mongo(fhir_status: str) -> str:
    """
    Map FHIR appointment status to MongoDB status
    """
    status_map = {
        'proposed': 'requested',
        'pending': 'requested',
        'booked': 'confirmed',
        'arrived': 'confirmed',
        'fulfilled': 'completed',
        'cancelled': 'cancelled',
        'noshow': 'cancelled'
    }
    return status_map.get(fhir_status, 'confirmed')


def appointment_to_fhir(appointment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB appointment document to FHIR R4 Appointment resource

    Args:
        appointment: MongoDB appointment document

    Returns:
        FHIR R4 Appointment resource
    """
    # Handle datetime formatting
    appt_datetime = appointment.get('appointmentDateTime')
    if isinstance(appt_datetime, datetime):
        start_time = appt_datetime.isoformat()
        # Calculate end time
        duration = appointment.get('duration', 60)
        end_time = (appt_datetime + timedelta(minutes=duration)).isoformat()
    else:
        start_time = str(appt_datetime) if appt_datetime else None
        end_time = str(appointment.get('endDateTime', '')) if appointment.get('endDateTime') else None

    # Get provider info
    provider_info = appointment.get('providerInfo', {})
    provider_name = f"Dr. {provider_info.get('lastName', 'Unknown')}" if provider_info.get(
        'lastName') else "Unknown Provider"

    return {
        "resourceType": "Appointment",
        "id": str(appointment.get('_id', '')),
        "status": mongo_status_to_fhir(appointment.get('status', 'booked')),
        "serviceCategory": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/service-category",
                "code": "17",
                "display": "General Practice"
            }]
        }],
        "serviceType": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/service-type",
                "code": appointment.get('appointmentRoute', '').lower(),
                "display": appointment.get('appointmentRoute', 'General')
            }]
        }],
        "appointmentType": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0276",
                "code": "ROUTINE",
                "display": appointment.get('appointmentType', 'Routine')
            }]
        },
        "reasonCode": [{
            "text": appointment.get('reason', 'General consultation')
        }],
        "description": appointment.get('reason', ''),
        "start": start_time,
        "end": end_time,
        "minutesDuration": appointment.get('duration', 60),
        "created": appointment.get('createdAt', datetime.now(pytz.UTC)).isoformat() if isinstance(
            appointment.get('createdAt'), datetime) else str(appointment.get('createdAt', '')),
        "comment": appointment.get('reason', ''),
        "participant": [
            {
                "actor": {
                    "reference": f"Patient/{appointment.get('patientID', '')}",
                    "display": "Patient"
                },
                "required": "required",
                "status": "accepted"
            },
            {
                "actor": {
                    "reference": f"Practitioner/{appointment.get('doctorID', '')}",
                    "display": provider_name
                },
                "required": "required",
                "status": "accepted"
            }
        ],
        "meta": {
            "lastUpdated": appointment.get('updatedAt', datetime.now(UTC)).isoformat() if isinstance(
                appointment.get('updatedAt'), datetime) else str(appointment.get('updatedAt', ''))
        }
    }


def appointments_to_fhir_bundle(appointments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert list of MongoDB appointments to FHIR Bundle

    Args:
        appointments: List of MongoDB appointment documents

    Returns:
        FHIR R4 Bundle (searchset)
    """
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(appointments),
        "entry": [
            {
                "fullUrl": f"Appointment/{appointment.get('_id', '')}",
                "resource": appointment_to_fhir(appointment),
                "search": {
                    "mode": "match"
                }
            }
            for appointment in appointments
        ]
    }
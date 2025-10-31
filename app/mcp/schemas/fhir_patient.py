# app/mcp/schemas/fhir_patient.py
"""
Convert MongoDB patient documents to FHIR R4 Patient resources
"""

from typing import Dict, Any
from datetime import datetime, UTC


def patient_to_fhir(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB patient document to FHIR R4 Patient resource

    Args:
        patient: MongoDB patient document

    Returns:
        FHIR R4 Patient resource
    """
    # Handle date of birth formatting
    dob = patient.get('dob')
    if isinstance(dob, datetime):
        dob_str = dob.strftime('%Y-%m-%d')
    else:
        dob_str = str(dob) if dob else None

    # Handle updatedAt formatting
    updated_at = patient.get('updatedAt')
    if isinstance(updated_at, datetime):
        last_updated = updated_at.isoformat()
    else:
        last_updated = datetime.now(UTC)

    return {
        "resourceType": "Patient",
        "id": str(patient.get('_id', '')),
        "identifier": [
            {
                "use": "official",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "MR",
                        "display": "Medical Record Number"
                    }]
                },
                "system": "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.0",
                "value": patient.get('accountNumber', '')
            }
        ],
        "active": True,
        "name": [{
            "use": "official",
            "family": patient.get('lastName', ''),
            "given": [patient.get('firstName', '')]
        }],
        "telecom": [
            {
                "system": "phone",
                "value": patient.get('mobileNumber', ''),
                "use": "mobile"
            }
        ],
        "gender": "unknown",
        "birthDate": dob_str,
        "address": [{
            "use": "home",
            "type": "physical",
            "line": [patient.get('streetAddress', '')],
            "city": patient.get('city', ''),
            "state": patient.get('state', ''),
            "postalCode": patient.get('postCode', ''),
            "country": "US"
        }],
        "meta": {
            "lastUpdated": last_updated  # Fixed - now using the variable we created above
        }
    }
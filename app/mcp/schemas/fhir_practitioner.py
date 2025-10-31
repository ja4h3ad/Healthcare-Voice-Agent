# app/mcp/schemas/fhir_practitioner.py
"""
Convert MongoDB physician/physician assistant documents to FHIR R4 Practitioner resources
"""

from typing import Dict, Any


def provider_to_fhir(provider: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB provider document to FHIR R4 Practitioner resource

    Args:
        provider: MongoDB physician or physician assistant document

    Returns:
        FHIR R4 Practitioner resource
    """
    provider_type = provider.get('providerType', 'Unknown')

    return {
        "resourceType": "Practitioner",
        "id": str(provider.get('_id', '')),
        "active": True,
        "name": [{
            "use": "official",
            "family": provider.get('lastName', ''),
            "given": [provider.get('firstName', '')],
            "prefix": ["Dr."] if provider_type == "Physician" else []
        }],
        "qualification": [{
            "code": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0360",
                    "code": "MD" if provider_type == "Physician" else "RN",
                    "display": provider_type
                }],
                "text": provider.get('specialty', 'General Practice')
            }
        }]
    }
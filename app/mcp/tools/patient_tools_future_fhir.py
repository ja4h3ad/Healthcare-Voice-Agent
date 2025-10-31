# app/mcp/tools/patient_tools.py (FHIR version)

import httpx
import json

FHIR_BASE_URL = "https://your-fhir-server.com/fhir"


async def get_patient_by_phone_tool(phone: str) -> str:
    """
    Query real FHIR server for patient by phone
    """
    async with httpx.AsyncClient() as client:
        # FHIR search: GET [base]/Patient?telecom=phone|{number}
        response = await client.get(
            f"{FHIR_BASE_URL}/Patient",
            params={"telecom": f"phone|{phone}"},
            headers={"Accept": "application/fhir+json"}
        )

        if response.status_code == 200:
            bundle = response.json()
            if bundle.get('total', 0) > 0:
                # Return first patient
                return json.dumps(bundle['entry'][0]['resource'], indent=2)

        return json.dumps({
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "not-found",
                "diagnostics": f"No patient found"
            }]
        })